"""
Бизнес-правила рабочей нагрузки сотрудника.

Единственный источник правды для ограничений CRM:

* :data:`MAX_IN_PROGRESS_TASKS` — сколько задач сотрудник может
  одновременно держать в статусе «в работе». По ТЗ — ровно одна:
  «один сотрудник может взять только одну задачу одновременно».

* :data:`MAX_ACTIVE_TASKS` — сколько всего задач у сотрудника может
  находиться в любых «живых» статусах (``new`` / ``in_progress`` /
  ``waiting``). По ТЗ — не более двух.

* :data:`MAX_ACTIVE_REQUESTS` — сколько заявок клиентов сотрудник
  может одновременно вести (заявка в статусе ``processing``).
  По ТЗ — не более двух, чтобы один агент не «забрал всех клиентов».

* :data:`ACTIVE_TASK_STATUS_CODES` / :data:`ACTIVE_REQUEST_STATUS_CODES`
  — коды статусов, считающиеся «активной загрузкой».

Правила применяются и на уровне API (при ``take`` / ``start`` /
создании задачи), и на уровне бизнес-слоя (функции ниже),
а фронтенд получает ту же информацию через ``/users/me/workload/``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db.models import Q

from . import models


# --------------------------------------------------------------------- limits

MAX_IN_PROGRESS_TASKS = 1
MAX_ACTIVE_TASKS = 2
MAX_ACTIVE_REQUESTS = 2

ACTIVE_TASK_STATUS_CODES: tuple[str, ...] = ('new', 'in_progress', 'waiting')
IN_PROGRESS_TASK_STATUS_CODES: tuple[str, ...] = ('in_progress',)
ACTIVE_REQUEST_STATUS_CODES: tuple[str, ...] = ('processing',)


class WorkloadLimitExceeded(Exception):
    """Попытка превысить один из лимитов рабочей нагрузки."""

    def __init__(self, detail: str, code: str = 'workload_limit'):
        super().__init__(detail)
        self.detail = detail
        self.code = code


# ------------------------------------------------------------------ querysets

def active_tasks_qs(user, *, exclude_pk: int | None = None):
    """Активные (не завершённые и не отменённые) задачи сотрудника."""
    qs = models.Task.objects.filter(
        assignee=user,
        status__code__in=ACTIVE_TASK_STATUS_CODES,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def in_progress_tasks_qs(user, *, exclude_pk: int | None = None):
    """Задачи сотрудника, которые он прямо сейчас выполняет."""
    qs = models.Task.objects.filter(
        assignee=user,
        status__code__in=IN_PROGRESS_TASK_STATUS_CODES,
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


# ------------------------------------------------------------------ snapshots

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


def snapshot_for(user) -> WorkloadSnapshot:
    """Построить срез нагрузки для сотрудника."""
    return WorkloadSnapshot(
        active_tasks=active_tasks_qs(user).count(),
        in_progress_tasks=in_progress_tasks_qs(user).count(),
        active_requests=active_requests_qs(user).count(),
    )


# -------------------------------------------------------------------- asserts

def assert_can_take_request(user, *, exclude_pk: int | None = None) -> None:
    """Гарантирует, что сотрудник не превысит лимит активных заявок."""
    count = active_requests_qs(user, exclude_pk=exclude_pk).count()
    if count >= MAX_ACTIVE_REQUESTS:
        raise WorkloadLimitExceeded(
            f'Нельзя взять заявку: уже {count} активных '
            f'(максимум {MAX_ACTIVE_REQUESTS}). Закройте одну из '
            'текущих, чтобы принять новую.',
            code='max_active_requests',
        )


def assert_can_assign_task(user, *, exclude_pk: int | None = None) -> None:
    """Гарантирует, что сотруднику можно добавить ещё одну активную задачу."""
    count = active_tasks_qs(user, exclude_pk=exclude_pk).count()
    if count >= MAX_ACTIVE_TASKS:
        raise WorkloadLimitExceeded(
            f'Нельзя назначить задачу: у сотрудника уже {count} '
            f'активных задач (максимум {MAX_ACTIVE_TASKS}).',
            code='max_active_tasks',
        )


def assert_can_start_task(user, task) -> None:
    """
    Перед переводом задачи в ``in_progress`` проверяет,
    что у сотрудника нет другой «в работе».
    """
    count = in_progress_tasks_qs(user, exclude_pk=task.pk).count()
    if count >= MAX_IN_PROGRESS_TASKS:
        raise WorkloadLimitExceeded(
            'У сотрудника уже есть задача в работе. Сначала '
            'завершите или поставьте её на паузу (статус «Ожидание»).',
            code='max_in_progress_tasks',
        )


# --------------------------------------------------------------------- helper

def status_by_code(model, code: str):
    """Удобная выборка статуса по коду."""
    return model.objects.filter(code=code).first()
