"""
Универсальный сервис действий над задачами.

Вызывается и REST-эндпоинтом ``TaskViewSet.complete`` / ``record_step``,
и движком доменных событий при автозакрытии. Гарантирует:

* идемпотентность — уже завершённую задачу повторно не трогаем и
  не создаём дублирующие шаги;
* атомарность — все изменения внутри одной транзакции;
* единый источник правды для поля ``result`` (текстовое саммари) и
  ``steps_log`` (структурированный журнал этапов).

Подсистема KPI намеренно НЕ вызывается отсюда: её модель
(``EmployeeKPI``, поля ``kind``/``duration_sec``) ещё не создана в
БД. Когда KPI будет подключён, достаточно добавить вызов
``kpi.record_completion(task, ...)`` в конец :func:`complete_task`.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from . import models


def _get_status_by_code(code: str) -> models.TaskStatus | None:
    return models.TaskStatus.objects.filter(code=code).first()


def _normalize_result(result: Any) -> tuple[str | None, dict[str, Any]]:
    """
    Привести пользовательский ``result`` к паре ``(summary_text, meta_dict)``.

    Фронтенд присылает либо строку («текстовый результат»), либо объект
    ``{summary, steps, ...}`` — и то, и другое должно работать.
    Возвращаемая пара кладётся соответственно в ``Task.result``
    (TextField) и в ``Task.steps_log`` при необходимости.
    """
    if result is None:
        return None, {}
    if isinstance(result, str):
        stripped = result.strip()
        return (stripped or None), {}
    if isinstance(result, dict):
        summary = result.get('summary') or result.get('text')
        if summary is not None:
            summary = str(summary).strip() or None
        # Всё, что не summary, сохраняем как мета (не перетирая summary).
        meta = {k: v for k, v in result.items()
                if k not in ('summary', 'text')}
        return summary, meta
    # Неожиданный тип — приводим к строке для сохранности данных.
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
    """
    Перевести задачу в статус «Выполнено» и зафиксировать мета-данные.

    Возвращает ``(task, was_completed_now)``. Если задача уже была в
    терминальном статусе — ``was_completed_now=False``, повторные
    побочные эффекты НЕ выполняются. Это защищает от двойного клика
    и от случая, когда сигнал пришёл после ручного завершения.
    """
    # Перечитываем с блокировкой, чтобы параллельный вызов (например,
    # двойной клик в UI) увидел актуальный статус и не создал дубль.
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

    # --- result (TextField): человеческое описание итога ------------------
    # Если agent передал свой текст — перезаписываем. Если не передал,
    # но задача закрыта автоматически — ставим служебную формулировку,
    # чтобы в истории был виден источник.
    if summary_text:
        task.result = summary_text
    elif auto_closed and not task.result:
        task.result = reason or 'Автозакрыто системой.'

    # --- steps_log: финальный шаг «completed» -----------------------------
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

    # Hook for future KPI integration (см. docstring модуля).
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
    """
    Зафиксировать промежуточный этап выполнения задачи.

    Этапы бизнес-процесса (согласованы с фронтендом ``TaskWorkflow.vue``):
    ``contact`` — связался с клиентом,
    ``request`` — создал/открыл заявку,
    ``matching`` — подобрал объект / выполнил действие по заявке,
    ``completed`` — финальный шаг (пишется внутри :func:`complete_task`).

    Идемпотентности по шагу нет специально: сотрудник может
    повторить «позвонил» несколько раз (первый раз — «не дозвонился»,
    второй — «дозвонился»), и это корректная история.
    """
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
