"""Создание сделки по заявке."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from django.db import transaction
from django.utils import timezone

from . import models
from .documents import render_contract_pdf

logger = logging.getLogger(__name__)

DEFAULT_COMMISSION_PERCENT = 3.0

def _next_deal_number() -> str:
    """Следующий номер сделки вида ``D-YYYY-NNNN``."""
    year = timezone.now().year
    last_id = models.Deal.objects.order_by('-id').values_list('id', flat=True).first() or 0
    return f'D-{year}-{last_id + 1:04d}'


def _resolve_property_for_request(request_obj: models.Request) -> Optional[models.Property]:
    """Определяет объект сделки по заявке."""
    confirmed = (
        request_obj.matches
        .filter(is_confirmed=True, is_rejected=False)
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
        .order_by('id').first()
    )

@transaction.atomic
def create_deal_from_request(
    request_obj: models.Request,
    *,
    actor=None,
    generate_contract: bool = True,
) -> Optional[models.Deal]:
    """Создаёт сделку и при необходимости договор."""
    existing = models.Deal.objects.filter(request=request_obj).first()
    if existing:
        if generate_contract and not existing.contract_file:
            _attach_contract(existing)
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
    )

    if generate_contract:
        _attach_contract(deal)

    logger.info(
        'Создана сделка %s по заявке #%s (объект #%s, клиент #%s).',
        deal.deal_number, request_obj.pk, prop.pk, request_obj.client_id,
    )
    return deal


def _attach_contract(deal: models.Deal) -> None:
    """Генерирует PDF и сохраняет его в ``deal.contract_file``."""
    try:
        pdf = render_contract_pdf(deal)
    except Exception:  # pragma: no cover
        logger.exception(
            'Не удалось сгенерировать договор для сделки %s', deal.deal_number,
        )
        return
    deal.contract_file.save(pdf.name, pdf, save=False)
    deal.contract_generated_at = timezone.now()
    deal.save(update_fields=['contract_file', 'contract_generated_at'])
