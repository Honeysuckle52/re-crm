"""
Доменные сигналы приложения ``key``.

Централизованное место для автоматизаций на уровне бизнес-процессов:
* автоматическое создание задачи «Связаться с клиентом» при взятии заявки;
* автозакрытие задач типа «property_search» при подтверждении варианта;
* создание исходящего письма клиенту при подтверждении варианта.
"""
from datetime import timedelta

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.utils import timezone

from . import models
from .business_rules import ACTIVE_TASK_STATUS_CODES
from .mailing import enqueue_property_matched, enqueue_request_taken
from .task_actions import complete_task


# ============================================================================
# Кастомные сигналы
# ============================================================================

# Сигнал «вариант подтверждён агентом» — вызывается из views.py
# при действии confirm_property на RequestPropertyMatch.
property_match_confirmed = Signal()


# ============================================================================
# Кеширование предыдущих значений для post_save
# ============================================================================

_AGENT_CACHE_ATTR = '_previous_agent_id'


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


# ============================================================================
# Автосоздание задачи при взятии заявки
# ============================================================================

@receiver(post_save, sender=models.Request)
def request_taken_create_task(sender, instance, created, **kwargs):
    """
    При назначении агента заявке автоматически создаёт задачу
    «Связаться с клиентом» с приоритетом high и сроком +24 часа.

    Триггер:
      * заявка уже существовала и agent_id сменился с None на значение;
      * новая заявка сразу создана с агентом (редкий случай — сотрудник
        вносит заявку за клиента и сразу берёт её на себя).
    """
    previous_agent_id = getattr(instance, _AGENT_CACHE_ATTR, None)
    if not instance.agent_id:
        return
    if not created and previous_agent_id == instance.agent_id:
        return

    # Защита от повторного создания, если сигнал дважды сработал.
    if instance.tasks.filter(
            title__startswith='Связаться с клиентом',
            assignee_id=instance.agent_id).exists():
        return

    status_new = models.TaskStatus.objects.filter(code='new').first()
    if not status_new:
        return

    client_name = getattr(instance.client, 'username', 'клиентом')
    property_title = (
        instance.property.title if instance.property_id and instance.property
        else None
    )
    description_lines = [
        f'Свяжитесь с клиентом {client_name} по заявке №{instance.pk}.',
    ]
    if property_title:
        description_lines.append(f'Интересует объект: {property_title}.')
    if instance.description:
        description_lines.append(f'Пожелания клиента: {instance.description}')

    models.Task.objects.create(
        title=f'Связаться с клиентом по заявке №{instance.pk}',
        description='\n'.join(description_lines),
        priority='high',
        task_type='contact_client',
        status=status_new,
        assignee_id=instance.agent_id,
        created_by_id=instance.agent_id,
        client_id=instance.client_id,
        property_id=instance.property_id,
        request=instance,
        due_date=timezone.now() + timedelta(hours=24),
    )
    # Уведомляем клиента, что заявка принята в работу.
    enqueue_request_taken(request=instance, agent=instance.agent)


# ============================================================================
# Автозакрытие задач «подбор объектов» + отправка письма
# ============================================================================

@receiver(property_match_confirmed)
def auto_close_search_task_and_send_email(sender, match, confirmed_by, **kwargs):
    """
    При подтверждении варианта подборки:
    1. Автоматически закрывает активные задачи типа 'property_search'
       по этой заявке и записывает результат.
    2. Создаёт исходящее письмо клиенту с информацией о выбранном объекте.
    3. Записывает в статистику сотрудника (через completed_at и result).
    """
    request_obj = match.request
    property_obj = match.property

    # --- 1. Автозакрытие задач типа property_search ---
    active_search_tasks = models.Task.objects.filter(
        request=request_obj,
        task_type='property_search',
        status__code__in=ACTIVE_TASK_STATUS_CODES,
    )
    for task in active_search_tasks:
        complete_task(
            task,
            actor=confirmed_by,
            auto_closed=True,
            reason=(
                f'Автозакрыто: клиент подтвердил вариант '
                f'«{property_obj.title or "Объект №" + str(property_obj.pk)}» '
                f'по заявке №{request_obj.pk}.'
            ),
        )

    # --- 2. Создание исходящего письма клиенту ---
    enqueue_property_matched(
        request=request_obj,
        property_obj=property_obj,
        agent=confirmed_by,
    )
