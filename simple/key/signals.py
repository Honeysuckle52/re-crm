"""
Доменные сигналы приложения ``key``.

Централизованное место для автоматизаций на уровне бизнес-процессов:
например, автоматическое создание задачи «Связаться с клиентом» при
взятии заявки в работу.
"""
from datetime import timedelta

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from . import models


# Ключ для хранения «предыдущего» agent_id в экземпляре модели между
# pre_save и post_save. Использовать дополнительное свойство проще,
# чем повторно читать из БД в post_save.
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
    # Если заявка только что создана и агент указан — создаём задачу.
    # Если существовала и agent стал не-null — тоже.
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
        # Справочник не заполнен — молча выходим, чтобы не ломать flow.
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
        status=status_new,
        assignee_id=instance.agent_id,
        created_by_id=instance.agent_id,
        client_id=instance.client_id,
        property_id=instance.property_id,
        request=instance,
        due_date=timezone.now() + timedelta(hours=24),
    )
