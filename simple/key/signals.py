"""
Доменные сигналы приложения ``key``.

Здесь два класса сигналов:

1. Django-сигналы жизненного цикла моделей (``pre_save`` /
   ``post_save``) — отвечают за детектирование событий в БД
   («агенту назначили заявку», «агент предложил вариант клиенту»).
2. Собственные доменные сигналы из :mod:`key.events` — через них
   API-слой явно объявляет факт («клиент принял вариант»,
   «просмотр проведён»). Их тоже обрабатываем здесь.

Ресиверы ДОЛЖНЫ быть быстрыми и не делать сетевых вызовов напрямую —
письма уходят асинхронно через ``key.mailing.enqueue_*``, которая
ставит задание на ``transaction.on_commit``.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from . import events, mailing, models, task_actions

log = logging.getLogger(__name__)


# Ключ для хранения «предыдущего» agent_id в экземпляре модели между
# pre_save и post_save.
_AGENT_CACHE_ATTR = '_previous_agent_id'


# ======================================================================
#  Автосоздание задачи «Связаться с клиентом»
# ======================================================================

@receiver(pre_save, sender=models.Request)
def _cache_previous_agent(sender, instance, **kwargs):
    """Запоминает значение agent_id до сохранения — чтобы понять,
    это ли «первое взятие в работу»."""
    if instance.pk:
        try:
            previous = sender.objects.only('agent_id').get(pk=instance.pk)
            setattr(instance, _AGENT_CACHE_ATTR, previous.agent_id)
        except sender.DoesNotExist:
            setattr(instance, _AGENT_CACHE_ATTR, None)
    else:
        setattr(instance, _AGENT_CACHE_ATTR, None)


@receiver(post_save, sender=models.Request)
def request_taken_create_task(sender, instance, created, **kwargs):
    """
    При назначении агента заявке автоматически создаёт задачу
    «Связаться с клиентом» (``kind=call``) и — если клиент ищет
    объект под себя — ещё и задачу «Подбор объектов» с
    ``auto_close_rule=on_property_matched``.
    """
    previous_agent_id = getattr(instance, _AGENT_CACHE_ATTR, None)
    if not instance.agent_id:
        return
    if not created and previous_agent_id == instance.agent_id:
        return

    status_new = models.TaskStatus.objects.filter(code='new').first()
    if not status_new:
        return

    client_name = getattr(instance.client, 'username', 'клиентом')
    property_title = (
        instance.property.title if instance.property_id and instance.property
        else None
    )

    # --- Звонок клиенту -------------------------------------------------
    if not instance.tasks.filter(
            kind=models.Task.KIND_CALL,
            assignee_id=instance.agent_id).exists():
        desc = [
            f'Свяжитесь с клиентом {client_name} по заявке №{instance.pk}.',
        ]
        if property_title:
            desc.append(f'Интересует объект: {property_title}.')
        if instance.description:
            desc.append(f'Пожелания клиента: {instance.description}')

        models.Task.objects.create(
            title=f'Связаться с клиентом по заявке №{instance.pk}',
            description='\n'.join(desc),
            kind=models.Task.KIND_CALL,
            priority='high',
            status=status_new,
            assignee_id=instance.agent_id,
            created_by_id=instance.agent_id,
            client_id=instance.client_id,
            property_id=instance.property_id,
            request=instance,
            due_date=timezone.now() + timedelta(hours=24),
        )

    # --- Подбор объектов для клиента ------------------------------------
    # Создаётся только если клиент ищет объект (у заявки нет
    # конкретного property) — задача будет автоматически закрыта,
    # когда агент подберёт и подтвердит вариант.
    if (not instance.property_id
            and not instance.tasks.filter(
                kind=models.Task.KIND_PROPERTY_SEARCH,
                assignee_id=instance.agent_id).exists()):
        models.Task.objects.create(
            title=f'Подобрать объект клиенту по заявке №{instance.pk}',
            description=(f'Подберите подходящий объект для клиента '
                         f'{client_name}.'),
            kind=models.Task.KIND_PROPERTY_SEARCH,
            auto_close_rule=models.Task.AUTO_CLOSE_ON_PROPERTY_MATCHED,
            priority='normal',
            status=status_new,
            assignee_id=instance.agent_id,
            created_by_id=instance.agent_id,
            client_id=instance.client_id,
            request=instance,
            due_date=timezone.now() + timedelta(days=3),
        )


# ======================================================================
#  Автоматика по домену: «клиент подобран / объект подобран»
# ======================================================================

def _close_tasks(queryset, *, actor, reason: str) -> list[models.Task]:
    """Закрывает набор задач и возвращает реально закрытые."""
    closed: list[models.Task] = []
    for task in queryset:
        completed_task, was_closed = task_actions.complete_task(
            task, actor=actor, auto_closed=True, reason=reason,
        )
        if was_closed:
            closed.append(completed_task)
    return closed


@receiver(events.request_client_matched)
def _on_client_matched(sender, *, request, property, agent,
                       match=None, **kwargs):
    """
    Агент подобрал клиенту подходящий объект / клиент принял вариант.

    Закрываем все открытые задачи по этой заявке с типами
    ``property_search`` или ``client_search`` (если они настроены на
    автозакрытие) и запускаем отправку письма клиенту.
    """
    if request is None:
        return

    qs = (models.Task.objects
          .select_related('status')
          .filter(request=request)
          .exclude(status__code__in=models.Task.TERMINAL_STATUS_CODES)
          .filter(
              kind__in=[
                  models.Task.KIND_PROPERTY_SEARCH,
                  models.Task.KIND_CLIENT_SEARCH,
              ],
          ))
    closed = _close_tasks(qs, actor=agent, reason='client_matched')

    # Запись «что именно подобрали» — удобно для журнала.
    for task in closed:
        result = dict(task.result or {})
        result.setdefault('matched_property_id',
                          getattr(property, 'pk', None))
        result.setdefault('matched_property_title',
                          getattr(property, 'title', None))
        if match is not None:
            result.setdefault('match_id', getattr(match, 'pk', None))
        models.Task.objects.filter(pk=task.pk).update(result=result)

    # Письмо клиенту с рабочего ящика — асинхронно, через on_commit.
    try:
        mailing.enqueue_property_matched(
            request=request,
            property_obj=property,
            agent=agent,
            trigger_task=closed[0] if closed else None,
        )
    except Exception:  # noqa: BLE001
        # Любая ошибка подготовки письма НЕ должна откатывать смену
        # статусов задач. Подробности фиксируются в логи и журнал
        # OutgoingEmail (status='failed').
        log.exception('Не удалось поставить письмо в очередь отправки')


@receiver(events.viewing_completed)
def _on_viewing_completed(sender, *, viewing, agent=None,
                          client=None, **kwargs):
    qs = (models.Task.objects
          .select_related('status')
          .filter(property_id=viewing.property_id,
                  client_id=viewing.client_id,
                  kind=models.Task.KIND_VIEWING)
          .exclude(status__code__in=models.Task.TERMINAL_STATUS_CODES))
    _close_tasks(qs, actor=agent, reason='viewing_done')


@receiver(events.deal_created)
def _on_deal_created(sender, *, deal, agent=None, client=None, **kwargs):
    qs = (models.Task.objects
          .select_related('status')
          .filter(client_id=deal.client_id,
                  property_id=deal.property_id)
          .exclude(status__code__in=models.Task.TERMINAL_STATUS_CODES)
          .filter(
              kind__in=[
                  models.Task.KIND_CLIENT_SEARCH,
                  models.Task.KIND_PROPERTY_SEARCH,
                  models.Task.KIND_DOCUMENTS,
              ]))
    _close_tasks(qs, actor=agent, reason='deal_created')


@receiver(events.request_closed)
def _on_request_closed(sender, *, request, actor=None, **kwargs):
    qs = (models.Task.objects
          .select_related('status')
          .filter(request=request)
          .exclude(status__code__in=models.Task.TERMINAL_STATUS_CODES))
    _close_tasks(qs, actor=actor, reason='request_closed')


# ======================================================================
#  Триггер «агент предложил вариант клиенту» → request_client_matched
# ======================================================================

@receiver(post_save, sender=models.RequestPropertyMatch)
def _match_created_triggers_event(sender, instance, created, **kwargs):
    """
    Любое создание варианта подборки (``RequestPropertyMatch``) = «агент
    нашёл клиенту объект». Этого достаточно, чтобы закрыть задачу
    «Подобрать объект». При необходимости более консервативной логики
    («закрываем только когда клиент сам подтвердил вариант») —
    триггер переключается на ручной эндпоинт ``accept_match``,
    который тоже отправляет :data:`events.request_client_matched`.
    """
    if not created:
        return
    if instance.is_rejected:
        return
    events.request_client_matched.send(
        sender=sender,
        request=instance.request,
        property=instance.property,
        agent=instance.agent,
        match=instance,
    )
