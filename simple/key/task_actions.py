"""
Универсальный сервис завершения задач.

Используется и REST-эндпоинтом ``TaskViewSet.complete``, и движком
доменных событий при автозакрытии. Гарантирует:

* идемпотентность — уже завершённую задачу не трогаем повторно;
* атомарность — смена статуса + запись KPI в одной транзакции;
* единый источник правды для расчёта ``duration_sec`` и ``result``.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from . import kpi, models


def _get_status_by_code(code: str) -> models.TaskStatus | None:
    return models.TaskStatus.objects.filter(code=code).first()


@transaction.atomic
def complete_task(
    task: models.Task,
    *,
    actor=None,
    auto_closed: bool = False,
    reason: str | None = None,
    result: dict[str, Any] | None = None,
) -> tuple[models.Task, bool]:
    """
    Перевести задачу в статус «Выполнено» и зафиксировать KPI.

    Возвращает ``(task, was_completed_now)``. Если задача уже была в
    терминальном статусе — ``was_completed_now=False``, повторная
    запись KPI НЕ делается.
    """
    # Перечитываем с блокировкой, чтобы параллельный вызов (например,
    # двойной клик в UI) не создал двойную запись в KPI.
    task = (models.Task.objects
            .select_for_update()
            .select_related('status', 'assignee')
            .get(pk=task.pk))

    if task.is_terminal:
        return task, False

    done = _get_status_by_code('done')
    if done is not None:
        task.status = done

    now = timezone.now()
    task.completed_at = now
    if task.created_at:
        delta = now - task.created_at
        task.duration_sec = max(int(delta.total_seconds()), 0)

    merged_result: dict[str, Any] = dict(task.result or {})
    if result:
        merged_result.update(result)
    if auto_closed:
        merged_result.setdefault('auto_closed', True)
        if reason:
            merged_result.setdefault('auto_closed_by', reason)
    if actor is not None and getattr(actor, 'pk', None):
        merged_result.setdefault('closed_by_user_id', actor.pk)
        merged_result.setdefault('closed_by_username',
                                 getattr(actor, 'username', None))
    merged_result.setdefault('closed_at', now.isoformat())
    task.result = merged_result

    task.save(update_fields=[
        'status', 'completed_at', 'duration_sec', 'result', 'updated_at',
    ])

    kpi.record_completion(task, auto_closed=auto_closed)
    return task, True
