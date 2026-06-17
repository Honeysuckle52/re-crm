# -*- coding: utf-8 -*-
"""Действия над задачами."""
from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import audit as audit_service
from . import models
from . import task_workflow


def _get_status_by_code(code: str) -> models.TaskStatus | None:
    return models.TaskStatus.objects.filter(code=code).first()


def _normalize_result(result: Any) -> tuple[str | None, dict[str, Any]]:
    """Нормализует ``result`` к виду ``(summary, meta)``."""
    if result is None:
        return None, {}
    if isinstance(result, str):
        stripped = result.strip()
        return (stripped or None), {}
    if isinstance(result, dict):
        summary = result.get('summary') or result.get('text')
        if summary is not None:
            summary = str(summary).strip() or None
        meta = {k: v for k, v in result.items()
                if k not in ('summary', 'text')}
        return summary, meta
    return str(result), {}


@transaction.atomic
def complete_task(
    task: models.Task,
    *,
    actor=None,
    auto_closed: bool = False,
    reason: str | None = None,
    result: Any = None,
) -> tuple[models.Task, bool]:
    """Завершает задачу и пишет итог в журнал."""
    task = (models.Task.objects
            .select_for_update()
            .select_related('status', 'assignee')
            .get(pk=task.pk))

    if task.is_terminal:
        return task, False

    if task.task_type == models.Task.TASK_TYPE_SHOWING and task.property_id and task.client_id:
        viewing = models.PropertyViewing.objects.select_related('status').filter(
            property_id=task.property_id,
            client_profile__user_id=task.client_id,
        ).order_by('-viewing_date', '-id').first()
        payment = getattr(viewing, 'payment', None) if viewing else None
        if payment is None or payment.status != models.ViewingPayment.STATUS_PAID:
            raise ValidationError({
                'detail': 'Нельзя завершить задачу показа, пока оплата просмотра не подтверждена.',
            })

    summary_text, meta = _normalize_result(result)

    done = _get_status_by_code('done')
    if done is not None:
        task.status = done

    now = timezone.now()
    task.completed_at = now

    if summary_text:
        task.result = summary_text
    elif auto_closed and not task.result:
        task.result = reason or 'Автозакрыто системой.'

    steps: list = list(task.steps_log or [])
    final_step = {
        'step': 'completed',
        'outcome': 'auto' if auto_closed else 'done',
        'note': summary_text or reason or '',
        'at': now.isoformat(),
        'by': getattr(actor, 'pk', None),
        'by_username': getattr(actor, 'username', None),
    }
    if meta:
        final_step['meta'] = meta
    steps.append(final_step)
    task.steps_log = steps

    if auto_closed:
        task.is_auto_closed = True

    try:
        task.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(
            exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages},
        ) from exc
    task.save(update_fields=[
        'status', 'completed_at', 'result', 'steps_log',
        'is_auto_closed', 'updated_at',
    ])
    audit_service.log_event(
        entity=task,
        action_code='completed',
        action_label='Завершение задачи',
        actor=actor,
        message=(
            'Задача автоматически закрыта системой.'
            if auto_closed else
            'Задача завершена.'
        ),
        metadata={
            'auto_closed': auto_closed,
            'result': summary_text or task.result or '',
            'task_type': task.task_type,
        },
        property_obj=task.property,
        request_obj=task.request,
        deal_obj=task.deal,
    )
    return task, True


@transaction.atomic
def record_step(
    task: models.Task,
    *,
    step: str,
    outcome: str | None = None,
    note: str | None = None,
    actor=None,
) -> models.Task:
    """Добавляет шаг в ``steps_log``."""
    task = (models.Task.objects
            .select_for_update()
            .get(pk=task.pk))

    normalized_step = (step or '').strip()
    normalized_outcome = (outcome or '').strip()
    task_workflow.validate_record_step(
        task,
        step=normalized_step,
        outcome=normalized_outcome,
    )

    entry: dict[str, Any] = {
        'step': normalized_step,
        'outcome': normalized_outcome,
        'note': (note or '').strip(),
        'at': timezone.now().isoformat(),
        'by': getattr(actor, 'pk', None),
        'by_username': getattr(actor, 'username', None),
    }
    steps = list(task.steps_log or [])
    steps.append(entry)
    task.steps_log = steps

    task.save(update_fields=['steps_log', 'updated_at'])
    workflow_steps = {
        workflow_step.get('id'): workflow_step
        for workflow_step in task_workflow.workflow_payload(task)
    }
    step_payload = workflow_steps.get(normalized_step, {})
    step_label = step_payload.get('label', normalized_step)
    outcome_label = next(
        (
            outcome_item.get('label') or normalized_outcome
            for outcome_item in step_payload.get('outcomes') or []
            if outcome_item.get('code') == normalized_outcome
        ),
        normalized_outcome,
    )
    audit_service.log_event(
        entity=task,
        action_code='workflow_step',
        action_label='Шаг workflow',
        actor=actor,
        message=(
            f'Зафиксирован этап «{step_label}»'
            + (f' с результатом «{outcome_label}».' if outcome_label else '.')
        ),
        metadata={
            'step': normalized_step,
            'outcome': normalized_outcome,
            'note': entry['note'],
        },
        property_obj=task.property,
        request_obj=task.request,
        deal_obj=task.deal,
    )
    return task
