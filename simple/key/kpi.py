"""
Запись и выборка KPI сотрудников.

Фиксация статистики идёт строго атомарно (``F('…') + 1``), чтобы при
параллельных завершениях задач счётчики не ломались. Выборки —
сгруппированные по дню и/или типу задачи: используются в
``/users/{id}/kpi/`` и в личном кабинете.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from . import models


def _is_enabled() -> bool:
    """KPI доступен, только если соответствующая модель существует."""
    return hasattr(models, 'EmployeeKPI')


def _resolve_duration_sec(task: models.Task) -> int:
    """Длительность выполнения задачи в секундах (не отрицательная)."""
    duration = getattr(task, 'duration_sec', None)
    if duration is not None:
        return max(int(duration), 0)
    if task.completed_at and task.created_at:
        delta = task.completed_at - task.created_at
        return max(int(delta.total_seconds()), 0)
    return 0


def _is_overdue(task: models.Task) -> bool:
    """Была ли задача просрочена в момент завершения."""
    if not task.due_date or not task.completed_at:
        return False
    return task.completed_at > task.due_date


@transaction.atomic
def record_completion(task: models.Task, *, auto_closed: bool = False) -> None:
    """
    Зафиксировать завершение задачи в KPI сотрудника.

    Идемпотентность обеспечивается на уровне вызывающего кода:
    ``TaskViewSet.complete`` не повторяет запись для уже терминальной
    задачи, а движок событий проверяет код статуса перед закрытием.
    """
    if not _is_enabled():
        return
    if not task.assignee_id or not task.completed_at:
        return

    day: date = timezone.localtime(task.completed_at).date()
    duration = _resolve_duration_sec(task)
    overdue_inc = 1 if _is_overdue(task) else 0
    auto_inc = 1 if auto_closed else 0

    task_kind = getattr(task, 'kind', None) or task.task_type or 'other'
    row, created = models.EmployeeKPI.objects.get_or_create(
        employee_id=task.assignee_id,
        period=day,
        kind=task_kind,
        defaults={
            'completed_count': 1,
            'auto_closed_count': auto_inc,
            'overdue_count': overdue_inc,
            'total_duration_sec': duration,
        },
    )
    if created:
        return

    models.EmployeeKPI.objects.filter(pk=row.pk).update(
        completed_count=F('completed_count') + 1,
        auto_closed_count=F('auto_closed_count') + auto_inc,
        overdue_count=F('overdue_count') + overdue_inc,
        total_duration_sec=F('total_duration_sec') + duration,
    )


# ------------------------------------------------------------------ читалки

def kpi_for_range(
    employee_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """
    Агрегированная статистика сотрудника за интервал дат.

    Возвращает словарь формата, удобного фронтенду:
    ``{ totals: {...}, by_kind: [...], by_day: [...] }``.
    """
    if not _is_enabled():
        return {
            'date_from': (date_from or timezone.localdate()).isoformat(),
            'date_to': (date_to or timezone.localdate()).isoformat(),
            'totals': {
                'completed': 0, 'auto_closed': 0, 'overdue': 0,
                'total_duration_sec': 0, 'avg_duration_sec': 0,
            },
            'by_kind': [],
            'by_day': [],
        }
    today = timezone.localdate()
    date_from = date_from or (today - timedelta(days=30))
    date_to = date_to or today

    qs = models.EmployeeKPI.objects.filter(
        employee_id=employee_id,
        period__gte=date_from,
        period__lte=date_to,
    )

    totals = qs.aggregate(
        completed=Sum('completed_count'),
        auto_closed=Sum('auto_closed_count'),
        overdue=Sum('overdue_count'),
        duration=Sum('total_duration_sec'),
    )

    by_kind_raw = (qs.values('kind')
                     .annotate(
                         completed=Sum('completed_count'),
                         auto_closed=Sum('auto_closed_count'),
                         overdue=Sum('overdue_count'),
                         duration=Sum('total_duration_sec'),
                     )
                     .order_by('-completed'))
    kind_labels = dict(models.Task.TASK_TYPE_CHOICES)
    by_kind = [{
        'kind': row['kind'],
        'kind_label': kind_labels.get(row['kind'], row['kind']),
        'completed': row['completed'] or 0,
        'auto_closed': row['auto_closed'] or 0,
        'overdue': row['overdue'] or 0,
        'total_duration_sec': row['duration'] or 0,
    } for row in by_kind_raw]

    by_day_raw = (qs.values('period')
                    .annotate(
                        completed=Sum('completed_count'),
                        auto_closed=Sum('auto_closed_count'),
                        overdue=Sum('overdue_count'),
                    )
                    .order_by('period'))
    by_day = [{
        'date': row['period'].isoformat(),
        'completed': row['completed'] or 0,
        'auto_closed': row['auto_closed'] or 0,
        'overdue': row['overdue'] or 0,
    } for row in by_day_raw]

    completed = totals['completed'] or 0
    duration = totals['duration'] or 0
    avg_sec = int(duration / completed) if completed else 0

    return {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'totals': {
            'completed': completed,
            'auto_closed': totals['auto_closed'] or 0,
            'overdue': totals['overdue'] or 0,
            'total_duration_sec': duration,
            'avg_duration_sec': avg_sec,
        },
        'by_kind': by_kind,
        'by_day': by_day,
    }


def today_snapshot(employee_id: int) -> dict:
    """Короткая сводка «сегодня» — выводится в виджете текущей задачи."""
    if not _is_enabled():
        return {
            'completed_today': 0,
            'auto_closed_today': 0,
            'overdue_today': 0,
            'avg_duration_sec': 0,
        }
    day = timezone.localdate()
    totals = (models.EmployeeKPI.objects
              .filter(employee_id=employee_id, period=day)
              .aggregate(
                  completed=Sum('completed_count'),
                  auto_closed=Sum('auto_closed_count'),
                  overdue=Sum('overdue_count'),
                  duration=Sum('total_duration_sec'),
              ))
    completed = totals['completed'] or 0
    duration = totals['duration'] or 0
    return {
        'completed_today': completed,
        'auto_closed_today': totals['auto_closed'] or 0,
        'overdue_today': totals['overdue'] or 0,
        'avg_duration_sec': int(duration / completed) if completed else 0,
    }
