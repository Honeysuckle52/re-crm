"""
Сервис исходящих писем клиентам.

Модуль синхронизирован с актуальной моделью ``OutgoingEmail``:
запись в таблицу-журнал + асинхронная SMTP-отправка в фоне.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from . import models

log = logging.getLogger(__name__)

TEMPLATE_PROPERTY_MATCHED = 'property_matched'
TEMPLATE_REQUEST_TAKEN = 'request_taken'
TEMPLATE_REQUEST_CLOSED = 'request_closed'
TEMPLATE_TASK_ASSIGNED = 'task_assigned'
TEMPLATE_TASK_ASSIGNED_CALL = 'task_assigned_call'
TEMPLATE_TASK_ASSIGNED_SHOWING = 'task_assigned_showing'
TEMPLATE_TASK_ASSIGNED_DOCUMENTS = 'task_assigned_documents'


# ---------------------------------------------------------------- низкий API

def _render(template: str, ctx: dict[str, Any]) -> tuple[str, str, str]:
    """Возвращает (subject, text, html) из шаблонов emails/<template>/*."""
    base = f'emails/{template}'
    subject = render_to_string(f'{base}/subject.txt', ctx).strip()
    text = render_to_string(f'{base}/body.txt', ctx)
    try:
        html = render_to_string(f'{base}/body.html', ctx)
    except Exception:  # noqa: BLE001 — html-шаблон опционален
        html = ''
    return subject, text, html


def _task_template_by_type(task_type: str) -> str:
    """
    Подбор шаблона уведомления по типу задачи.

    Если специализированного шаблона нет, используем универсальный.
    """
    mapping = {
        'call': TEMPLATE_TASK_ASSIGNED_CALL,
        'showing': TEMPLATE_TASK_ASSIGNED_SHOWING,
        'documents': TEMPLATE_TASK_ASSIGNED_DOCUMENTS,
    }
    return mapping.get(task_type, TEMPLATE_TASK_ASSIGNED)


def _audit_context(
    *,
    trigger_code: str,
    template_code: str,
    request: models.Request | None,
    task: models.Task | None,
    property_obj: models.Property | None,
) -> dict[str, Any]:
    """Единая структура аудита отправки, сохраняемая в OutgoingEmail.context."""
    return {
        'trigger_code': trigger_code,
        'template_code': template_code,
        'request_id': getattr(request, 'pk', None),
        'task_id': getattr(task, 'pk', None),
        'property_id': getattr(property_obj, 'pk', None),
    }


def _send_via_smtp(email: models.OutgoingEmail) -> None:
    """Синхронная отправка. Вызывается из фонового потока."""
    msg = EmailMultiAlternatives(
        email.subject,
        email.body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email.recipient.email],
        reply_to=[settings.AGENCY_REPLY_TO] if getattr(settings, 'AGENCY_REPLY_TO', '') else None,
    )
    msg.send(fail_silently=False)


def _dispatch(email_id: int) -> None:
    """Фоновая обёртка: грузит запись, шлёт, обновляет журнал."""
    try:
        email = models.OutgoingEmail.objects.get(pk=email_id)
    except models.OutgoingEmail.DoesNotExist:
        return
    if email.status != 'pending':
        return
    try:
        _send_via_smtp(email)
    except Exception as exc:  # noqa: BLE001 — логируем любую ошибку SMTP
        log.exception('SMTP send failed for email=%s', email_id)
        models.OutgoingEmail.objects.filter(pk=email_id).update(
            status='failed',
            error_message=str(exc)[:2000],
        )
        return
    models.OutgoingEmail.objects.filter(pk=email_id).update(
        status='sent',
        sent_at=timezone.now(),
        error_message=None,
    )


def _spawn_thread(email_id: int) -> None:
    threading.Thread(
        target=_dispatch,
        args=(email_id,),
        name=f'outgoing-email-{email_id}',
        daemon=True,
    ).start()


# ---------------------------------------------------------------- высокий API

def enqueue_property_matched(
    *,
    request: models.Request,
    property_obj: models.Property,
    agent: models.User,
    trigger_task: models.Task | None = None,
) -> models.OutgoingEmail | None:
    """
    Поставить в очередь письмо «для вас подобран подходящий объект».

    Письмо НЕ отправляется, если у клиента не указан e-mail —
    в журнал пишем сразу статус ``cancelled`` с пояснением.
    """
    client = request.client

    ctx = {
        'agency_name': settings.AGENCY_NAME,
        'public_url': settings.AGENCY_PUBLIC_URL,
        'client_name': (client.username if client else 'уважаемый клиент'),
        'client_email': (client.email or '').strip() if client else '',
        'property': property_obj,
        'property_url': (
            f'{settings.AGENCY_PUBLIC_URL.rstrip("/")}/properties/'
            f'{property_obj.pk}'
        ),
        'request': request,
        'request_url': (
            f'{settings.AGENCY_PUBLIC_URL.rstrip("/")}/requests/'
            f'{request.pk}'
        ),
        'agent': agent,
        'agent_name': getattr(agent, 'username', '') if agent else '',
        'agent_email': (getattr(agent, 'email', '') or '') if agent else '',
        'agent_phone': (getattr(agent, 'phone', '') or '') if agent else '',
    }

    return _enqueue_by_template(
        template=TEMPLATE_PROPERTY_MATCHED,
        trigger_code='property_match_confirmed',
        context=ctx,
        recipient=client,
        sender=agent,
        task=trigger_task,
        request=request,
        property_obj=property_obj,
    )


def _enqueue_by_template(
    *,
    template: str,
    trigger_code: str,
    context: dict[str, Any],
    recipient: models.User | None,
    sender: models.User | None = None,
    task: models.Task | None = None,
    request: models.Request | None = None,
    property_obj: models.Property | None = None,
) -> models.OutgoingEmail | None:
    """Унифицированная постановка шаблонного письма в очередь."""
    to_email = (getattr(recipient, 'email', '') or '').strip()
    if not recipient or not to_email:
        return None
    subject, text, html = _render(template, context)
    email = models.OutgoingEmail.objects.create(
        recipient=recipient,
        sender=sender if sender and getattr(sender, 'is_employee', False) else None,
        subject=subject,
        body=text if not html else f'{text}\n\n---- HTML ----\n{html}',
        template_code=template,
        trigger_code=trigger_code,
        context=_audit_context(
            trigger_code=trigger_code,
            template_code=template,
            request=request,
            task=task,
            property_obj=property_obj,
        ),
        task=task,
        request=request,
        property=property_obj,
        status='pending',
    )
    log.info(
        'Email queued: trigger=%s template=%s recipient=%s request=%s task=%s property=%s',
        trigger_code, template, recipient.pk, getattr(request, 'pk', None),
        getattr(task, 'pk', None), getattr(property_obj, 'pk', None),
    )
    transaction.on_commit(lambda: _spawn_thread(email.pk))
    return email


def enqueue_request_taken(*, request: models.Request, agent: models.User) -> models.OutgoingEmail | None:
    """Клиенту: заявка взята в работу сотрудником."""
    client = request.client
    ctx = {
        'agency_name': settings.AGENCY_NAME,
        'public_url': settings.AGENCY_PUBLIC_URL,
        'client_name': getattr(client, 'username', 'клиент'),
        'request': request,
        'agent': agent,
        'agent_name': getattr(agent, 'username', ''),
        'agent_email': (getattr(agent, 'email', '') or ''),
        'agent_phone': (getattr(agent, 'phone', '') or ''),
        'request_url': f'{settings.AGENCY_PUBLIC_URL.rstrip("/")}/requests/{request.pk}',
    }
    return _enqueue_by_template(
        template=TEMPLATE_REQUEST_TAKEN,
        trigger_code='request_taken',
        context=ctx,
        recipient=client,
        sender=agent,
        request=request,
        property_obj=request.property,
    )


def enqueue_request_closed(
    *,
    request: models.Request,
    actor: models.User | None = None,
    deal: models.Deal | None = None,
) -> models.OutgoingEmail | None:
    """Клиенту: заявка закрыта, опционально добавляем ссылку на сделку."""
    client = request.client
    ctx = {
        'agency_name': settings.AGENCY_NAME,
        'public_url': settings.AGENCY_PUBLIC_URL,
        'client_name': getattr(client, 'username', 'клиент'),
        'request': request,
        'deal': deal,
        'has_deal': bool(deal),
        'request_url': f'{settings.AGENCY_PUBLIC_URL.rstrip("/")}/requests/{request.pk}',
    }
    return _enqueue_by_template(
        template=TEMPLATE_REQUEST_CLOSED,
        trigger_code='request_closed',
        context=ctx,
        recipient=client,
        sender=actor,
        request=request,
        property_obj=request.property,
    )


def enqueue_task_assigned(*, task: models.Task) -> models.OutgoingEmail | None:
    """Сотруднику: назначена новая задача."""
    assignee = task.assignee
    if not assignee or not getattr(assignee, 'is_employee', False):
        return None
    ctx = {
        'agency_name': settings.AGENCY_NAME,
        'public_url': settings.AGENCY_PUBLIC_URL,
        'assignee_name': getattr(assignee, 'username', 'сотрудник'),
        'task': task,
        'task_url': f'{settings.AGENCY_PUBLIC_URL.rstrip("/")}/tasks',
        'request': task.request,
        'property': task.property,
    }
    template_code = _task_template_by_type(task.task_type)
    return _enqueue_by_template(
        template=template_code,
        trigger_code='task_assigned',
        context=ctx,
        recipient=assignee,
        sender=task.created_by,
        task=task,
        request=task.request,
        property_obj=task.property,
    )


def resend(email: models.OutgoingEmail) -> None:
    """Повторная отправка для статусов failed/cancelled."""
    if email.status == 'sent':
        return
    recipient_email = (getattr(email.recipient, 'email', '') or '').strip()
    if not recipient_email:
        return
    models.OutgoingEmail.objects.filter(pk=email.pk).update(
        status='pending',
        error_message=None,
    )
    log.info(
        'Email re-queued: id=%s trigger=%s template=%s',
        email.pk, email.trigger_code, email.template_code,
    )
    transaction.on_commit(lambda: _spawn_thread(email.pk))
