# -*- coding: utf-8 -*-
"""Лимиты нагрузки сотрудников."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db.models import Q

from . import models


MAX_IN_PROGRESS_TASKS = 1
MAX_ACTIVE_TASKS = 2
MAX_ACTIVE_REQUESTS = 2

ACTIVE_TASK_STATUS_CODES: tuple[str, ...] = ('new', 'in_progress', 'waiting')
IN_PROGRESS_TASK_STATUS_CODES: tuple[str, ...] = ('in_progress',)
ACTIVE_REQUEST_STATUS_CODES: tuple[str, ...] = models.Request.ACTIVE_STATUS_CODES
PROPERTY_FINAL_STATUS_BY_OPERATION: dict[str, str] = {
    'sale': 'sold',
    'rent': 'rented',
}
PROPERTY_STATUS_TRANSITIONS: dict[str, set[str]] = {
    'pending': {'active', 'archived'},
    'active': {'reserved', 'archived'},
    'reserved': {'active', 'archived'},
    'sold': {'archived'},
    'rented': {'archived'},
    'archived': {'active'},
}
DEAL_STATUS_TRANSITIONS: dict[str, set[str]] = {
    'new': {'negotiation', 'cancelled'},
    'negotiation': {'new', 'documents', 'cancelled'},
    'documents': {'negotiation', 'signed', 'cancelled'},
    'signed': {'documents', 'completed', 'cancelled'},
    'completed': set(),
    'cancelled': set(),
}


class WorkloadLimitExceeded(Exception):
    """Попытка превысить один из лимитов рабочей нагрузки."""

    def __init__(self, detail: str, code: str = 'workload_limit'):
        super().__init__(detail)
        self.detail = detail
        self.code = code


def active_tasks_qs(user, *, exclude_pk: int | None = None):
    """Активные (не завершённые и не отменённые) задачи сотрудника."""
    qs = models.Task.objects.filter(
        assignee=user,
        status__code__in=ACTIVE_TASK_STATUS_CODES,
        completed_at__isnull=True,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def in_progress_tasks_qs(user, *, exclude_pk: int | None = None):
    """Задачи сотрудника, которые он прямо сейчас выполняет."""
    qs = models.Task.objects.filter(
        assignee=user,
        status__code__in=IN_PROGRESS_TASK_STATUS_CODES,
        completed_at__isnull=True,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def active_requests_qs(user, *, exclude_pk: int | None = None):
    """Активные (в работе) заявки клиентов, закреплённые за сотрудником."""
    qs = models.Request.objects.filter(
        agent=user,
        status__code__in=ACTIVE_REQUEST_STATUS_CODES,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs


@dataclass
class WorkloadSnapshot:
    """Срез текущей загрузки сотрудника — для API и UI."""
    active_tasks: int
    in_progress_tasks: int
    active_requests: int
    max_active_tasks: int = MAX_ACTIVE_TASKS
    max_in_progress_tasks: int = MAX_IN_PROGRESS_TASKS
    max_active_requests: int = MAX_ACTIVE_REQUESTS

    @property
    def can_take_request(self) -> bool:
        return self.active_requests < self.max_active_requests

    @property
    def can_take_task(self) -> bool:
        return self.active_tasks < self.max_active_tasks

    @property
    def can_start_task(self) -> bool:
        return self.in_progress_tasks < self.max_in_progress_tasks

    def as_dict(self) -> dict:
        return {
            'active_tasks': self.active_tasks,
            'in_progress_tasks': self.in_progress_tasks,
            'active_requests': self.active_requests,
            'max_active_tasks': self.max_active_tasks,
            'max_in_progress_tasks': self.max_in_progress_tasks,
            'max_active_requests': self.max_active_requests,
            'can_take_request': self.can_take_request,
            'can_take_task': self.can_take_task,
            'can_start_task': self.can_start_task,
        }


def resolve_workload_limits(user) -> dict[str, int]:
    """Возвращает действующие лимиты сотрудника с учётом его роли."""
    role = getattr(user, 'role', None)

    def _limit(attr_name: str, default: int) -> int:
        if role is None:
            return default
        value = getattr(role, attr_name, None)
        if value is None:
            return default
        return int(value)

    return {
        'max_active_tasks': _limit('max_active_tasks', MAX_ACTIVE_TASKS),
        'max_in_progress_tasks': _limit(
            'max_in_progress_tasks',
            MAX_IN_PROGRESS_TASKS,
        ),
        'max_active_requests': _limit(
            'max_active_requests',
            MAX_ACTIVE_REQUESTS,
        ),
    }


def snapshot_for(user) -> WorkloadSnapshot:
    """Построить срез нагрузки для сотрудника."""
    limits = resolve_workload_limits(user)
    return WorkloadSnapshot(
        active_tasks=active_tasks_qs(user).count(),
        in_progress_tasks=in_progress_tasks_qs(user).count(),
        active_requests=active_requests_qs(user).count(),
        max_active_tasks=limits['max_active_tasks'],
        max_in_progress_tasks=limits['max_in_progress_tasks'],
        max_active_requests=limits['max_active_requests'],
    )


def assert_can_take_request(user, *, exclude_pk: int | None = None) -> None:
    """Гарантирует, что сотрудник не превысит лимит активных заявок."""
    limits = resolve_workload_limits(user)
    max_active_requests = limits['max_active_requests']
    count = active_requests_qs(user, exclude_pk=exclude_pk).count()
    if count >= max_active_requests:
        raise WorkloadLimitExceeded(
            f'Нельзя взять заявку: уже {count} активных '
            f'(максимум {max_active_requests}). Закройте одну из '
            'текущих, чтобы принять новую.',
            code='max_active_requests',
        )


def assert_can_assign_task(user, *, exclude_pk: int | None = None) -> None:
    """Гарантирует, что сотруднику можно добавить ещё одну активную задачу."""
    limits = resolve_workload_limits(user)
    max_active_tasks = limits['max_active_tasks']
    count = active_tasks_qs(user, exclude_pk=exclude_pk).count()
    if count >= max_active_tasks:
        raise WorkloadLimitExceeded(
            f'Нельзя назначить задачу: у сотрудника уже {count} '
            f'активных задач (максимум {max_active_tasks}).',
            code='max_active_tasks',
        )


def assert_can_start_task(user, task) -> None:
    """
    Перед переводом задачи в ``in_progress`` проверяет,
    что у сотрудника нет другой «в работе».
    """
    limits = resolve_workload_limits(user)
    max_in_progress_tasks = limits['max_in_progress_tasks']
    count = in_progress_tasks_qs(user, exclude_pk=task.pk).count()
    if count >= max_in_progress_tasks:
        raise WorkloadLimitExceeded(
            f'Нельзя перевести задачу в работу: уже {count} '
            f'задач в работе (максимум {max_in_progress_tasks}). '
            'Сначала завершите одну из них или поставьте на паузу.',
            code='max_in_progress_tasks',
        )


def status_by_code(model, code: str):
    """Удобная выборка статуса по коду."""
    return model.objects.filter(code=code).first()


def property_status_transition_error(property_obj, next_status) -> str | None:
    """Вернуть текст ошибки, если переход статуса объекта недопустим."""
    current_code = getattr(property_obj.status, 'code', None)
    next_code = getattr(next_status, 'code', None)
    if not current_code or not next_code or current_code == next_code:
        return None

    allowed_codes = PROPERTY_STATUS_TRANSITIONS.get(current_code)
    if allowed_codes is None:
        return None

    allowed = set(allowed_codes)
    if current_code in {'active', 'reserved'}:
        operation_code = getattr(property_obj.operation_type, 'code', None)
        terminal_code = PROPERTY_FINAL_STATUS_BY_OPERATION.get(operation_code)
        if terminal_code:
            allowed.add(terminal_code)
        else:
            allowed.update({'sold', 'rented'})

        if next_code in {'sold', 'rented'} and terminal_code and next_code != terminal_code:
            operation_name = getattr(property_obj.operation_type, 'name', 'Текущая операция')
            expected_name = 'Продано' if terminal_code == 'sold' else 'Сдано'
            return (
                f'Для операции «{operation_name}» объект можно завершить '
                f'только статусом «{expected_name}».'
            )

    if next_code in allowed:
        return None

    return (
        f'Нельзя перевести объект из статуса «{property_obj.status.name}» '
        f'в «{next_status.name}».'
    )


def property_allowed_transition_codes(property_obj) -> tuple[str, ...]:
    """Коды статусов объекта, допустимые для UI, включая текущий."""
    current_code = getattr(property_obj.status, 'code', None)
    if not current_code:
        return ()

    allowed_codes = PROPERTY_STATUS_TRANSITIONS.get(current_code)
    if allowed_codes is None:
        return (current_code,)

    allowed = set(allowed_codes)
    if current_code in {'active', 'reserved'}:
        operation_code = getattr(property_obj.operation_type, 'code', None)
        terminal_code = PROPERTY_FINAL_STATUS_BY_OPERATION.get(operation_code)
        if terminal_code:
            allowed.add(terminal_code)
        else:
            allowed.update({'sold', 'rented'})

    ordered = [current_code]
    ordered.extend(code for code in allowed if code != current_code)
    return tuple(ordered)


def deal_status_transition_error(deal, next_status) -> str | None:
    """Вернуть текст ошибки, если переход статуса сделки недопустим."""
    current_code = getattr(deal.status, 'code', None)
    next_code = getattr(next_status, 'code', None)
    if not current_code or not next_code or current_code == next_code:
        return None

    allowed = DEAL_STATUS_TRANSITIONS.get(current_code)
    if allowed is None or next_code in allowed:
        return None

    return (
        f'Нельзя перевести сделку из статуса «{deal.status.name}» '
        f'в «{next_status.name}».'
    )


def deal_allowed_transition_codes(deal) -> tuple[str, ...]:
    """Коды статусов сделки, допустимые для UI, включая текущий."""
    current_code = getattr(deal.status, 'code', None)
    if not current_code:
        return ()

    allowed = DEAL_STATUS_TRANSITIONS.get(current_code)
    if allowed is None:
        return (current_code,)

    ordered = [current_code]
    ordered.extend(code for code in allowed if code != current_code)
    return tuple(ordered)
