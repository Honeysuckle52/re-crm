"""Действия над задачами."""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from . import models
from . import kpi


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

    task.save(update_fields=[
        'status', 'completed_at', 'result', 'steps_log',
        'is_auto_closed', 'updated_at',
    ])

    kpi.record_completion(task, auto_closed=auto_closed)
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

    entry: dict[str, Any] = {
        'step': step,
        'outcome': outcome or '',
        'note': (note or '').strip(),
        'at': timezone.now().isoformat(),
        'by': getattr(actor, 'pk', None),
        'by_username': getattr(actor, 'username', None),
    }
    steps = list(task.steps_log or [])
    steps.append(entry)
    task.steps_log = steps

    task.save(update_fields=['steps_log', 'updated_at'])
    return task
