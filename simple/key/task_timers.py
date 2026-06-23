# -*- coding: utf-8 -*-
"""Автоматические переходы статусов задач по времени."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import audit as audit_service
from . import business_rules, models

STALE_NEW_TASK_AFTER = timedelta(days=3)


def apply_task_timeouts(*, now=None, queryset=None) -> dict[str, int]:
    now = now or timezone.now()
    waiting_status = business_rules.status_by_code(models.TaskStatus, 'waiting')
    cancelled_status = business_rules.status_by_code(models.TaskStatus, 'cancelled')
    if cancelled_status is None:
        return {'moved_to_waiting': 0, 'cancelled': 0}

    base_qs = queryset or models.Task.objects.select_related(
        'status', 'assignee', 'created_by', 'property', 'request', 'deal',
    )
    tasks = list(base_qs.filter(completed_at__isnull=True))
    moved_to_waiting = 0
    cancelled = 0

    for task in tasks:
        status_code = getattr(task.status, 'code', None)
        update_fields = ['status', 'updated_at']
        action_code = None
        action_label = None
        message = None
        metadata = {}

        if waiting_status and task.due_date and task.due_date <= now and status_code == 'new':
            task.status = waiting_status
            action_code = 'auto_waiting'
            action_label = 'Автоперевод задачи в ожидание'
            message = 'Задача автоматически переведена в ожидание после наступления срока.'
            metadata = {'reason': 'due_date_passed', 'to_status_code': waiting_status.code}
            moved_to_waiting += 1
        elif status_code == 'new' and task.created_at <= now - STALE_NEW_TASK_AFTER:
            task.status = cancelled_status
            task.completed_at = now
            task.is_auto_closed = True
            update_fields.extend(['completed_at', 'is_auto_closed'])
            action_code = 'auto_cancelled'
            action_label = 'Автоотмена неактивной задачи'
            message = 'Задача автоматически отменена из-за отсутствия действий по ней.'
            metadata = {'reason': 'stale_new_task', 'to_status_code': cancelled_status.code}
            cancelled += 1
        else:
            continue

        with transaction.atomic():
            task.save(update_fields=list(dict.fromkeys(update_fields)))
            audit_service.log_event(
                entity=task,
                action_code=action_code,
                action_label=action_label,
                actor=None,
                message=message,
                metadata=metadata,
                property_obj=task.property,
                request_obj=task.request,
                deal_obj=task.deal,
            )

    return {
        'moved_to_waiting': moved_to_waiting,
        'cancelled': cancelled,
    }
