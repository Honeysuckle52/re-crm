"""Сигналы и автоматизации по заявкам."""
from datetime import timedelta

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver, Signal
from django.utils import timezone

from . import models
from .business_rules import ACTIVE_TASK_STATUS_CODES
from .mailing import enqueue_property_matched, enqueue_request_taken
from .task_actions import complete_task

property_match_confirmed = Signal()

_AGENT_CACHE_ATTR = '_previous_agent_id'


@receiver(pre_save, sender=models.Request)
def _cache_previous_agent(sender, instance, **kwargs):
    """Запоминает старый ``agent_id`` перед сохранением."""
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
    """Создаёт задачу на первый контакт с клиентом."""
    previous_agent_id = getattr(instance, _AGENT_CACHE_ATTR, None)
    if not instance.agent_id:
        return
    if not created and previous_agent_id == instance.agent_id:
        return

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
    enqueue_request_taken(request=instance, agent=instance.agent)

@receiver(property_match_confirmed)
def auto_close_search_task_and_send_email(sender, match, confirmed_by, **kwargs):
    """Закрывает подборные задачи и ставит письмо в очередь."""
    request_obj = match.request
    property_obj = match.property

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

    enqueue_property_matched(
        request=request_obj,
        property_obj=property_obj,
        agent=confirmed_by,
    )
