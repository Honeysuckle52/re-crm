"""
Сервис исходящих писем клиентам.

Реализация сознательно простая: запись в ``OutgoingEmail`` (журнал) +
фоновая отправка в отдельном потоке через ``transaction.on_commit``.
Вынесение в Celery/django-q возможно позже — API функций останется
тем же.
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

# Код шаблона письма = имя папки в templates/emails/<code>/
TEMPLATE_PROPERTY_MATCHED = 'property_matched'


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


def _send_via_smtp(email: models.OutgoingEmail) -> None:
    """Синхронная отправка. Вызывается из фонового потока."""
    msg = EmailMultiAlternatives(
        email.subject,
        email.body_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email.to_email],
        reply_to=[settings.AGENCY_REPLY_TO] if settings.AGENCY_REPLY_TO else None,
        headers={
            'X-Entity-Ref-ID': (
                f'request-{email.related_request_id}'
                if email.related_request_id else
                f'task-{email.related_task_id or email.pk}'
            ),
        },
    )
    if email.body_html:
        msg.attach_alternative(email.body_html, 'text/html')
    msg.send(fail_silently=False)


def _dispatch(email_id: int) -> None:
    """Фоновая обёртка: грузит запись, шлёт, обновляет журнал."""
    try:
        email = models.OutgoingEmail.objects.get(pk=email_id)
    except models.OutgoingEmail.DoesNotExist:
        return
    if email.status != models.OutgoingEmail.STATUS_QUEUED:
        return
    try:
        _send_via_smtp(email)
    except Exception as exc:  # noqa: BLE001 — логируем любую ошибку SMTP
        log.exception('SMTP send failed for email=%s', email_id)
        models.OutgoingEmail.objects.filter(pk=email_id).update(
            status=models.OutgoingEmail.STATUS_FAILED,
            error=str(exc)[:2000],
            attempts=email.attempts + 1,
        )
        return
    models.OutgoingEmail.objects.filter(pk=email_id).update(
        status=models.OutgoingEmail.STATUS_SENT,
        sent_at=timezone.now(),
        attempts=email.attempts + 1,
        error=None,
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
    to_email = (client.email or '').strip() if client else ''

    ctx = {
        'agency_name': settings.AGENCY_NAME,
        'public_url': settings.AGENCY_PUBLIC_URL,
        'client_name': (client.username if client else 'уважаемый клиент'),
        'client_email': to_email,
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

    subject, text, html = _render(TEMPLATE_PROPERTY_MATCHED, ctx)

    if not to_email:
        # Нет e-mail — пишем запись-отметку, ничего не отправляем.
        return models.OutgoingEmail.objects.create(
            template=TEMPLATE_PROPERTY_MATCHED,
            to_email='',
            to_user=client,
            subject=subject,
            body_text=text,
            body_html=html,
            related_task=trigger_task,
            related_request=request,
            related_property=property_obj,
            status=models.OutgoingEmail.STATUS_CANCELLED,
            error='У клиента не указан e-mail',
        )

    email = models.OutgoingEmail.objects.create(
        template=TEMPLATE_PROPERTY_MATCHED,
        to_email=to_email,
        to_user=client,
        subject=subject,
        body_text=text,
        body_html=html,
        related_task=trigger_task,
        related_request=request,
        related_property=property_obj,
        status=models.OutgoingEmail.STATUS_QUEUED,
    )

    # Ставим отправку ПОСЛЕ коммита — иначе поток может не найти
    # запись, или транзакция откатится, а письмо уже улетит.
    transaction.on_commit(lambda: _spawn_thread(email.pk))
    return email


def resend(email: models.OutgoingEmail) -> None:
    """Повторная отправка для статусов failed/cancelled."""
    if email.status == models.OutgoingEmail.STATUS_SENT:
        return
    if not email.to_email:
        return
    models.OutgoingEmail.objects.filter(pk=email.pk).update(
        status=models.OutgoingEmail.STATUS_QUEUED,
        error=None,
    )
    transaction.on_commit(lambda: _spawn_thread(email.pk))
