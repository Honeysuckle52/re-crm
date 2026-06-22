# -*- coding: utf-8 -*-
"""Создание сделок и фоновая генерация договоров."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from django.db import connection, transaction, close_old_connections
from django.db import DatabaseError, OperationalError, InterfaceError
from django.db.models import Q
from django.utils import timezone

from . import audit as audit_service
from . import models
from .documents import render_contract_pdf

logger = logging.getLogger(__name__)

DEFAULT_COMMISSION_PERCENT = 3.0
CONTRACT_CLAIM_TIMEOUT = timedelta(minutes=15)


def _next_deal_number() -> str:
    """Следующий номер сделки вида ``D-YYYY-NNNN``."""
    year = timezone.now().year
    last_id = models.Deal.objects.order_by('-id').values_list('id', flat=True).first() or 0
    return f'D-{year}-{last_id + 1:04d}'


def _resolve_property_for_request(request_obj: models.Request) -> Optional[models.Property]:
    """Определяет объект сделки по заявке."""
    confirmed = (
        request_obj.matches
        .filter(status__code='confirmed')
        .select_related('property')
        .order_by('-confirmed_at', '-created_at')
        .first()
    )
    if confirmed:
        return confirmed.property

    if request_obj.property_id:
        return request_obj.property
    return None


def _resolve_agent(request_obj: models.Request, fallback_user) -> Optional[models.User]:
    """Берёт агента из заявки или подбирает запасной вариант."""
    if request_obj.agent_id:
        return request_obj.agent
    if fallback_user and getattr(fallback_user, 'is_employee', False):
        return fallback_user
    return (
        models.User.objects.filter(user_type='employee', is_active=True)
        .order_by('id')
        .first()
    )


def _deal_claim_queryset():
    queryset = models.Deal.objects.order_by('contract_requested_at', 'id')
    if connection.features.has_select_for_update:
        if connection.features.has_select_for_update_skip_locked:
            return queryset.select_for_update(skip_locked=True)
        return queryset.select_for_update()
    return queryset


@transaction.atomic
def queue_contract_generation(
    deal: models.Deal,
    *,
    force: bool = False,
    actor=None,
) -> models.Deal:
    """Ставит договор сделки в очередь на генерацию."""
    locked = models.Deal.objects.select_for_update().get(pk=deal.pk)
    now = timezone.now()
    update_fields = ['contract_status_ref', 'contract_error_message',
                     'contract_requested_at', 'contract_processing_started_at']

    if force and locked.contract_file:
        locked.contract_file.delete(save=False)
        locked.contract_file = None
        update_fields.append('contract_file')
    if force and locked.contract_generated_at is not None:
        locked.contract_generated_at = None
        update_fields.append('contract_generated_at')

    if locked.contract_file and not force:
        if locked.contract_status != 'ready':
            locked.contract_status = 'ready'
            locked.contract_error_message = None
            locked.contract_processing_started_at = None
            update_fields = ['contract_status_ref', 'contract_error_message',
                             'contract_processing_started_at']
            locked.save(update_fields=update_fields)
        return locked

    if not force and locked.contract_status in {'pending', 'processing'}:
        return locked

    locked.contract_status = 'pending'
    locked.contract_error_message = None
    locked.contract_requested_at = now
    locked.contract_processing_started_at = None
    locked.save(update_fields=list(dict.fromkeys(update_fields)))
    audit_service.log_event(
        entity=locked,
        action_code='contract_queued',
        action_label='Постановка договора в очередь',
        actor=actor,
        message='Генерация PDF-договора поставлена в очередь.',
        metadata={
            'force': force,
            'request_id': locked.request_id,
        },
        property_obj=locked.property,
        request_obj=locked.request,
    )
    return locked


def _claim_next_contract(
    *,
    stale_after: timedelta = CONTRACT_CLAIM_TIMEOUT,
) -> models.Deal | None:
    claim_time = timezone.now()
    cutoff = claim_time - stale_after
    eligible = (
        Q(contract_status='pending')
        | Q(contract_status='processing', contract_processing_started_at__lt=cutoff)
    )

    deal_id = None
    for attempt in range(2):
        try:
            with transaction.atomic():
                deal = _deal_claim_queryset().filter(eligible).first()
                if deal is None:
                    return None
                deal_id = deal.pk
                updated = models.Deal.objects.filter(pk=deal.pk).filter(eligible).update(
                    contract_status='processing',
                    contract_error_message=None,
                    contract_processing_started_at=claim_time,
                )
                if not updated:
                    return None
            break
        except (OperationalError, InterfaceError):
            close_old_connections()
            if attempt == 1:
                raise

    if deal_id is None:
        return None

    for attempt in range(2):
        try:
            return models.Deal.objects.select_related(
                'request', 'property', 'agent', 'client', 'operation_type', 'status',
            ).prefetch_related(
                'property__owners__client_profile__user',
                'property__owners__client_profile__individual_details',
                'property__owners__client_profile__company_details',
            ).get(pk=deal_id)
        except (OperationalError, InterfaceError):
            close_old_connections()
            if attempt == 1:
                raise


def _generate_contract_file(deal: models.Deal):
    """Генерирует PDF-файл договора для сделки."""
    return render_contract_pdf(deal)


def process_contract_queue(
    *,
    limit: int = 10,
    stale_after: timedelta = CONTRACT_CLAIM_TIMEOUT,
) -> dict[str, int]:
    """Обрабатывает очередь генерации договоров."""
    close_old_connections()
    summary = {
        'processed': 0,
        'generated': 0,
        'failed': 0,
    }

    for _ in range(max(limit, 0)):
        deal = _claim_next_contract(stale_after=stale_after)
        if deal is None:
            break

        summary['processed'] += 1
        try:
            pdf = _generate_contract_file(deal)
        except (OperationalError, InterfaceError, DatabaseError) as exc:
            logger.warning(
                'DB connection lost while generating contract for deal %s; retrying once',
                deal.deal_number,
            )
            close_old_connections()
            try:
                pdf = _generate_contract_file(deal)
            except Exception as retry_exc:  # noqa: BLE001
                exc = retry_exc
                logger.exception(
                    'Не удалось сгенерировать договор для сделки %s',
                    deal.deal_number,
                )
                models.Deal.objects.filter(pk=deal.pk).update(
                    contract_status='failed',
                    contract_error_message=str(exc)[:2000],
                    contract_processing_started_at=None,
                )
                audit_service.log_event(
                    entity=deal,
                    action_code='contract_failed',
                    action_label='Ошибка генерации договора',
                    actor=None,
                    message='Не удалось сформировать PDF-договор.',
                    metadata={
                        'error': str(exc)[:500],
                    },
                    property_obj=deal.property,
                    request_obj=deal.request,
                )
                summary['failed'] += 1
                continue
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                'Не удалось сгенерировать договор для сделки %s',
                deal.deal_number,
            )
            models.Deal.objects.filter(pk=deal.pk).update(
                contract_status='failed',
                contract_error_message=str(exc)[:2000],
                contract_processing_started_at=None,
            )
            audit_service.log_event(
                entity=deal,
                action_code='contract_failed',
                action_label='Ошибка генерации договора',
                actor=None,
                message='Не удалось сформировать PDF-договор.',
                metadata={
                    'error': str(exc)[:500],
                },
                property_obj=deal.property,
                request_obj=deal.request,
            )
            summary['failed'] += 1
            continue

        deal.contract_file.save(pdf.name, pdf, save=False)
        deal.contract_generated_at = timezone.now()
        deal.contract_status = 'ready'
        deal.contract_error_message = None
        deal.contract_processing_started_at = None
        deal.save(update_fields=[
            'contract_file',
            'contract_generated_at',
            'contract_status_ref',
            'contract_error_message',
            'contract_processing_started_at',
        ])
        audit_service.log_event(
            entity=deal,
            action_code='contract_ready',
            action_label='Генерация договора',
            actor=None,
            message='PDF-договор сформирован.',
            metadata={
                'generated_at': deal.contract_generated_at.isoformat(),
            },
            property_obj=deal.property,
            request_obj=deal.request,
        )
        summary['generated'] += 1

    return summary


@transaction.atomic
def create_deal_from_request(
    request_obj: models.Request,
    *,
    actor=None,
    generate_contract: bool = True,
) -> Optional[models.Deal]:
    """Создаёт сделку и при необходимости ставит договор в очередь."""
    existing = models.Deal.objects.filter(request=request_obj).first()
    if existing:
        if generate_contract and not existing.contract_file:
            return queue_contract_generation(existing, actor=actor)
        return existing

    prop = _resolve_property_for_request(request_obj)
    if prop is None:
        logger.info(
            'Не создаём сделку по заявке #%s: не найден объект '
            '(нет property и нет вариантов в подборке).',
            request_obj.pk,
        )
        return None

    agent = _resolve_agent(request_obj, actor)
    if agent is None:
        logger.warning(
            'Не создаём сделку по заявке #%s: нет ни одного сотрудника.',
            request_obj.pk,
        )
        return None

    status_new = models.DealStatus.objects.filter(code='new').first()

    commission_percent = DEFAULT_COMMISSION_PERCENT
    price = float(prop.price or 0)
    commission_amount = round(price * commission_percent / 100.0, 2) if price else None

    deal = models.Deal.objects.create(
        deal_number=_next_deal_number(),
        property=prop,
        agent=agent,
        client=request_obj.client,
        operation_type=request_obj.operation_type,
        status=status_new,
        request=request_obj,
        price_final=price,
        commission_percent=commission_percent,
        commission_amount=commission_amount,
        deal_date=date.today(),
        notes=(
            f'Сделка создана автоматически при закрытии заявки '
            f'#{request_obj.pk}.'
        ),
        contract_status='not_requested',
    )
    audit_service.log_event(
        entity=deal,
        action_code='created',
        action_label='Создание сделки',
        actor=actor,
        message=f'Сделка создана по заявке №{request_obj.pk}.',
        metadata={
            'request_id': request_obj.pk,
            'property_id': prop.pk,
            'client_id': request_obj.client_id,
        },
        property_obj=prop,
        request_obj=request_obj,
    )

    if generate_contract:
        deal = queue_contract_generation(deal, actor=actor)

    logger.info(
        'Создана сделка %s по заявке #%s (объект #%s, клиент #%s).',
        deal.deal_number, request_obj.pk, prop.pk, request_obj.client_id,
    )
    return deal
