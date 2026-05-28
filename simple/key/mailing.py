"""Очередь и отправка писем."""
from __future__ import annotations

import logging
import socket
import ssl
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import connection, transaction
from django.db.models import Q
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
LEGACY_HTML_MARKER = '\n\n---- HTML ----\n'
EMAIL_CLAIM_TIMEOUT = timedelta(minutes=15)


def _render(template: str, ctx: dict[str, Any]) -> tuple[str, str, str]:
    """Возвращает (subject, text, html) из статических шаблонов emails/<template>/*."""
    base = f'emails/{template}'
    subject = render_to_string(f'{base}/subject.txt', ctx).strip()
    text = render_to_string(f'{base}/body.txt', ctx)
    try:
        html = render_to_string(f'{base}/body.html', ctx)
    except Exception:  # noqa: BLE001 - html-шаблон опционален
        html = ''
    return subject, text, html


def _task_template_by_type(task_type: str) -> str:
    """Шаблон письма по типу задачи."""
    mapping = {
        'call': TEMPLATE_TASK_ASSIGNED_CALL,
        'showing': TEMPLATE_TASK_ASSIGNED_SHOWING,
        'documents': TEMPLATE_TASK_ASSIGNED_DOCUMENTS,
    }
    return mapping.get(task_type, TEMPLATE_TASK_ASSIGNED)


def _extract_bodies(email: models.OutgoingEmail) -> tuple[str, str]:
    """Возвращает plain-text и html с поддержкой старого формата хранения."""
    text = email.body or ''
    html = (getattr(email, 'html_body', '') or '').strip()
    if html:
        return text, html
    if LEGACY_HTML_MARKER in text:
        plain, legacy_html = text.split(LEGACY_HTML_MARKER, 1)
        return plain, legacy_html.strip()
    return text, ''


def _smtp_timeout() -> int:
    return int(getattr(settings, 'EMAIL_TIMEOUT', 30) or 30)


def _primary_smtp_config() -> dict[str, Any]:
    return {
        'backend': settings.EMAIL_BACKEND,
        'host': settings.EMAIL_HOST,
        'port': settings.EMAIL_PORT,
        'username': settings.EMAIL_HOST_USER,
        'password': settings.EMAIL_HOST_PASSWORD,
        'use_tls': settings.EMAIL_USE_TLS,
        'use_ssl': settings.EMAIL_USE_SSL,
        'timeout': _smtp_timeout(),
    }


def _fallback_smtp_config(primary: dict[str, Any]) -> dict[str, Any] | None:
    enabled = getattr(
        settings,
        'EMAIL_FALLBACK_ENABLED',
        bool(primary['use_ssl']) and not bool(primary['use_tls']),
    )
    if not enabled:
        return None

    config = {
        'backend': getattr(settings, 'EMAIL_FALLBACK_BACKEND', primary['backend']),
        'host': getattr(settings, 'EMAIL_FALLBACK_HOST', primary['host']),
        'port': int(
            getattr(
                settings,
                'EMAIL_FALLBACK_PORT',
                587 if primary['port'] == 465 else primary['port'],
            ),
        ),
        'username': getattr(settings, 'EMAIL_FALLBACK_USER', primary['username']),
        'password': getattr(settings, 'EMAIL_FALLBACK_PASSWORD', primary['password']),
        'use_tls': getattr(settings, 'EMAIL_FALLBACK_USE_TLS', True),
        'use_ssl': getattr(settings, 'EMAIL_FALLBACK_USE_SSL', False),
        'timeout': int(getattr(settings, 'EMAIL_FALLBACK_TIMEOUT', primary['timeout'])),
    }
    if (
        config['host'],
        config['port'],
        config['use_tls'],
        config['use_ssl'],
        config['username'],
    ) == (
        primary['host'],
        primary['port'],
        primary['use_tls'],
        primary['use_ssl'],
        primary['username'],
    ):
        return None
    return config


def _smtp_attempts() -> list[dict[str, Any]]:
    primary = _primary_smtp_config()
    attempts = [primary]
    fallback = _fallback_smtp_config(primary)
    if fallback is not None:
        attempts.append(fallback)
    return attempts


def _is_retryable_smtp_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (TimeoutError, socket.timeout, ConnectionError, OSError, ssl.SSLError),
    )


def _audit_context(
    *,
    trigger_code: str,
    request: models.Request | None,
    task: models.Task | None,
    property_obj: models.Property | None,
) -> dict[str, Any]:
    """Единая структура аудита отправки, сохраняемая в OutgoingEmail.context."""
    return {
        'trigger_code': trigger_code,
        'request_id': getattr(request, 'pk', None),
        'task_id': getattr(task, 'pk', None),
        'property_id': getattr(property_obj, 'pk', None),
    }


def _build_smtp_connection(config: dict[str, Any]):
    return get_connection(
        backend=config['backend'],
        host=config['host'],
        port=config['port'],
        username=config['username'],
        password=config['password'],
        use_tls=config['use_tls'],
        use_ssl=config['use_ssl'],
        timeout=config['timeout'],
        fail_silently=False,
    )


def _build_email_message(email: models.OutgoingEmail, *, connection_obj):
    text_body, html_body = _extract_bodies(email)

    msg = EmailMultiAlternatives(
        email.subject,
        text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email.recipient.email],
        reply_to=[settings.AGENCY_REPLY_TO] if getattr(settings, 'AGENCY_REPLY_TO', '') else None,
        connection=connection_obj,
    )
    if html_body:
        msg.attach_alternative(html_body, 'text/html')
    return msg


def _send_via_smtp(email: models.OutgoingEmail) -> None:
    """Отправляет письмо через SMTP с fallback на альтернативный канал."""
    attempts = _smtp_attempts()
    last_exc: Exception | None = None
    attempt_errors: list[str] = []

    for index, config in enumerate(attempts, start=1):
        connection_obj = _build_smtp_connection(config)
        msg = _build_email_message(email, connection_obj=connection_obj)
        old_default = socket.getdefaulttimeout()
        socket.setdefaulttimeout(config['timeout'])
        try:
            msg.send(fail_silently=False)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            attempt_errors.append(
                f"{config['host']}:{config['port']} ssl={config['use_ssl']} "
                f"tls={config['use_tls']} -> {exc}"
            )
            should_retry = (
                index < len(attempts)
                and _is_retryable_smtp_error(exc)
            )
            if should_retry:
                fallback = attempts[index]
                log.warning(
                    'SMTP primary channel failed for email=%s (%s:%s ssl=%s tls=%s): %s. '
                    'Retrying fallback channel %s:%s ssl=%s tls=%s.',
                    email.pk,
                    config['host'],
                    config['port'],
                    config['use_ssl'],
                    config['use_tls'],
                    exc,
                    fallback['host'],
                    fallback['port'],
                    fallback['use_ssl'],
                    fallback['use_tls'],
                )
                continue
            raise
        finally:
            socket.setdefaulttimeout(old_default)
            try:
                connection_obj.close()
            except Exception:  # noqa: BLE001
                pass
    if last_exc is not None:
        if len(attempt_errors) > 1:
            raise RuntimeError(' | '.join(attempt_errors)) from last_exc
        raise last_exc


def _email_claim_queryset():
    queryset = models.OutgoingEmail.objects.order_by('created_at', 'pk')
    if connection.features.has_select_for_update:
        if connection.features.has_select_for_update_skip_locked:
            return queryset.select_for_update(skip_locked=True)
        return queryset.select_for_update()
    return queryset


def _claim_next_email(
    *,
    stale_after: timedelta = EMAIL_CLAIM_TIMEOUT,
) -> models.OutgoingEmail | None:
    claim_time = timezone.now()
    cutoff = claim_time - stale_after
    eligible = (
        Q(status='pending')
        | Q(status='processing', processing_started_at__lt=cutoff)
    )

    with transaction.atomic():
        email = _email_claim_queryset().filter(eligible).first()
        if email is None:
            return None
        updated = models.OutgoingEmail.objects.filter(pk=email.pk).filter(
            eligible,
        ).update(
            status='processing',
            processing_started_at=claim_time,
            error_message=None,
        )
        if not updated:
            return None

    return models.OutgoingEmail.objects.select_related(
        'recipient', 'sender', 'task', 'request', 'property',
    ).get(pk=email.pk)


def process_email_queue(
    *,
    limit: int = 10,
    stale_after: timedelta = EMAIL_CLAIM_TIMEOUT,
) -> dict[str, int]:
    """Обрабатывает очередь исходящих писем."""
    summary = {
        'processed': 0,
        'sent': 0,
        'failed': 0,
    }

    for _ in range(max(limit, 0)):
        email = _claim_next_email(stale_after=stale_after)
        if email is None:
            break

        summary['processed'] += 1
        try:
            _send_via_smtp(email)
        except Exception as exc:  # noqa: BLE001
            log.exception('SMTP send failed for email=%s', email.pk)
            models.OutgoingEmail.objects.filter(pk=email.pk).update(
                status='failed',
                error_message=str(exc)[:2000],
                processing_started_at=None,
            )
            summary['failed'] += 1
            continue

        models.OutgoingEmail.objects.filter(pk=email.pk).update(
            status='sent',
            sent_at=timezone.now(),
            error_message=None,
            processing_started_at=None,
        )
        summary['sent'] += 1

    return summary


def enqueue_property_matched(
    *,
    request: models.Request,
    property_obj: models.Property,
    agent: models.User,
    trigger_task: models.Task | None = None,
) -> models.OutgoingEmail | None:
    """Письмо клиенту о подтверждённом варианте."""
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
    """Ставит шаблонное письмо в очередь."""
    to_email = (getattr(recipient, 'email', '') or '').strip()
    if not recipient or not to_email:
        return None
    subject, text, html = _render(template, context)
    email = models.OutgoingEmail.objects.create(
        recipient=recipient,
        sender=sender if sender and getattr(sender, 'is_employee', False) else None,
        subject=subject,
        body=text,
        html_body=html,
        trigger_code=trigger_code,
        context=_audit_context(
            trigger_code=trigger_code,
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
        'Email queued: trigger=%s recipient=%s request=%s task=%s property=%s',
        trigger_code, recipient.pk, getattr(request, 'pk', None),
        getattr(task, 'pk', None), getattr(property_obj, 'pk', None),
    )
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
    template_key = _task_template_by_type(task.task_type)
    return _enqueue_by_template(
        template=template_key,
        trigger_code='task_assigned',
        context=ctx,
        recipient=assignee,
        sender=task.created_by,
        task=task,
        request=task.request,
        property_obj=task.property,
    )


def resend(email: models.OutgoingEmail) -> None:
    """Повторная постановка письма в очередь."""
    if email.status == 'sent':
        return
    recipient_email = (getattr(email.recipient, 'email', '') or '').strip()
    if not recipient_email:
        return
    models.OutgoingEmail.objects.filter(pk=email.pk).update(
        status='pending',
        error_message=None,
        sent_at=None,
        processing_started_at=None,
    )
    log.info(
        'Email re-queued: id=%s trigger=%s',
        email.pk, email.trigger_code,
    )
