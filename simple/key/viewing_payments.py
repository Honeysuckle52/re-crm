# -*- coding: utf-8 -*-
"""Сервис оплаты просмотров через SmartPay поверх существующих таблиц."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import models
from .smartpay_service import SmartPayError, create_invoice, get_invoice_status, refund_invoice

SMARTPAY_STATUS_PENDING = {'CREATED', 'PENDING', 'NEW', 'WAITING_FOR_PAYMENT', 'ALREADY_CREATED'}
SMARTPAY_STATUS_PAID = {'PAID', 'SUCCESS', 'COMPLETED'}
SMARTPAY_STATUS_FAILED = {'CANCELLED', 'FAILED', 'DECLINED', 'EXPIRED'}
SMARTPAY_STATUS_REFUNDED = {'REFUNDED', 'PARTIALLY_REFUNDED'}


class ViewingPaymentError(Exception):
    """Базовая ошибка сервиса оплаты просмотров."""


class ViewingPaymentAccessDenied(ViewingPaymentError):
    """Ошибка прав доступа к оплате просмотра."""


class ViewingPaymentValidationError(ViewingPaymentError):
    """Ошибка бизнес-валидации при работе с оплатой просмотра."""


class SberAcquiringError(ViewingPaymentError):
    """Совместимое имя исключения для слоя views/task_actions."""


def _amount_to_kopecks(amount: Decimal) -> int:
    return int((amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _log_payment_history(
    payment: models.ViewingPayment,
    *,
    old_status: str | None,
    new_status: str,
    comment: str = '',
    provider_response: dict[str, Any] | None = None,
    changed_by=None,
) -> models.PaymentHistory:
    return models.PaymentHistory.objects.create(
        payment=payment,
        old_status=old_status,
        new_status=new_status,
        comment=comment or None,
        sber_response=provider_response or None,
        changed_by=changed_by,
    )


def calculate_viewing_amount(property_obj) -> Decimal:
    property_type = getattr(property_obj, 'premises_type', None) or models.Property.PROPERTY_TYPE_APARTMENT
    amount_map = getattr(settings, 'SMARTPAY_VIEWING_AMOUNTS', {}) or {}
    amount = amount_map.get(property_type)
    if amount is None:
        amount = amount_map.get(models.Property.PROPERTY_TYPE_APARTMENT, '500.00')
    if amount is None:
        amount = Decimal(getattr(settings, 'SMARTPAY_AMOUNT', 100)) / Decimal('100')
    return Decimal(str(amount)).quantize(Decimal('0.01'))


def _get_description(viewing: models.PropertyViewing) -> str:
    try:
        address = viewing.property.address
        address_str = str(address) if address else f'объект #{viewing.property_id}'
    except Exception:
        address_str = f'объект #{viewing.property_id}'
    return f'Предоплата просмотра недвижимости: {address_str}'


def _get_client_contacts(viewing: models.PropertyViewing) -> tuple[str | None, str | None]:
    user = viewing.client_profile.user
    return getattr(user, 'email', None) or None, getattr(user, 'phone', None) or None


def _normalize_provider_status(status: str | None) -> str:
    normalized = str(status or '').strip().upper()
    if normalized in SMARTPAY_STATUS_PAID:
        return models.ViewingPayment.STATUS_PAID
    if normalized in SMARTPAY_STATUS_FAILED:
        return models.ViewingPayment.STATUS_FAILED
    if normalized in SMARTPAY_STATUS_REFUNDED:
        return models.ViewingPayment.STATUS_REFUNDED
    return models.ViewingPayment.STATUS_PENDING


@transaction.atomic
def create_viewing_payment(viewing: models.PropertyViewing, actor, request) -> models.ViewingPayment:
    if not actor or not actor.is_authenticated or not actor.is_client:
        raise ViewingPaymentAccessDenied('Оплачивать просмотр может только авторизованный клиент.')
    if viewing.client_profile.user_id != actor.id:
        raise ViewingPaymentAccessDenied('Нельзя оплачивать чужой просмотр.')

    payment = getattr(viewing, 'payment', None)
    if payment and payment.status == models.ViewingPayment.STATUS_PAID:
        return payment

    amount = calculate_viewing_amount(viewing.property)
    old_status = None
    if payment is None:
        payment = models.ViewingPayment(
            viewing=viewing,
            client=actor,
            property=viewing.property,
            amount=amount,
            status=models.ViewingPayment.STATUS_PENDING,
        )
    else:
        old_status = payment.status
        payment.client = actor
        payment.property = viewing.property
        payment.amount = amount
        payment.status = models.ViewingPayment.STATUS_PENDING
        payment.paid_at = None
        payment.sber_transaction_id = None

    client_email, client_phone = _get_client_contacts(viewing)
    try:
        provider_response = create_invoice(
            viewing_id=viewing.pk,
            amount_kopecks=_amount_to_kopecks(amount),
            description=_get_description(viewing),
            client_email=client_email,
            client_phone=client_phone,
        )
    except SmartPayError as exc:
        raise SberAcquiringError(str(exc)) from exc

    invoice_id = provider_response.get('invoice_id')
    invoice_url = provider_response.get('invoice_url')
    if not invoice_id:
        raise SberAcquiringError('SmartPay не вернул invoice_id.')
    if not invoice_url:
        raise SberAcquiringError('SmartPay не вернул ссылку на оплату.')

    payment.sber_order_id = invoice_id
    payment.payment_url = invoice_url
    payment.status = _normalize_provider_status(provider_response.get('invoice_status'))
    payment.full_clean()
    payment.save()

    _log_payment_history(
        payment,
        old_status=old_status,
        new_status=payment.status,
        comment='Создан счёт SmartPay для оплаты просмотра.',
        provider_response=provider_response,
        changed_by=actor,
    )
    return payment


def fetch_smartpay_status(payment: models.ViewingPayment) -> dict[str, Any]:
    if not payment.sber_order_id:
        raise ViewingPaymentValidationError('У платежа отсутствует invoice_id SmartPay.')
    try:
        return get_invoice_status(payment.sber_order_id)
    except SmartPayError as exc:
        raise SberAcquiringError(str(exc)) from exc


@transaction.atomic
def mark_payment_paid(
    payment: models.ViewingPayment,
    provider_response: dict[str, Any],
    actor=None,
) -> models.ViewingPayment:
    payment = models.ViewingPayment.objects.select_for_update().get(pk=payment.pk)
    payment.viewing = (
        models.PropertyViewing.objects
        .select_related('status')
        .get(pk=payment.viewing_id)
    )
    old_status = payment.status
    payment.status = models.ViewingPayment.STATUS_PAID
    payment.paid_at = timezone.now()
    payment.sber_transaction_id = provider_response.get('transaction_id') or payment.sber_transaction_id
    if provider_response.get('invoice_url'):
        payment.payment_url = provider_response.get('invoice_url')
    payment.full_clean()
    payment.save(update_fields=['status', 'paid_at', 'sber_transaction_id', 'payment_url', 'updated_at'])

    confirmed_status = models.ViewingStatus.objects.filter(code='confirmed').first()
    if confirmed_status and payment.viewing.status_id != confirmed_status.pk:
        payment.viewing.status = confirmed_status
        payment.viewing.full_clean()
        payment.viewing.save(update_fields=['status'])

    _log_payment_history(
        payment,
        old_status=old_status,
        new_status=payment.status,
        comment='Оплата подтверждена по ответу SmartPay.',
        provider_response=provider_response,
        changed_by=actor,
    )
    return payment


@transaction.atomic
def mark_payment_failed(
    payment: models.ViewingPayment,
    provider_response: dict[str, Any] | None = None,
    actor=None,
    comment: str = '',
) -> models.ViewingPayment:
    payment = models.ViewingPayment.objects.select_for_update().get(pk=payment.pk)
    old_status = payment.status
    payment.status = models.ViewingPayment.STATUS_FAILED
    if provider_response and provider_response.get('invoice_url'):
        payment.payment_url = provider_response.get('invoice_url')
    payment.full_clean()
    payment.save(update_fields=['status', 'payment_url', 'updated_at'])
    _log_payment_history(
        payment,
        old_status=old_status,
        new_status=payment.status,
        comment=comment or 'SmartPay вернул неуспешный статус оплаты.',
        provider_response=provider_response,
        changed_by=actor,
    )
    return payment


@transaction.atomic
def mark_payment_refunded(
    payment: models.ViewingPayment,
    provider_response: dict[str, Any] | None = None,
    actor=None,
) -> models.ViewingPayment:
    payment = models.ViewingPayment.objects.select_for_update().get(pk=payment.pk)
    old_status = payment.status
    payment.status = models.ViewingPayment.STATUS_REFUNDED
    if provider_response and provider_response.get('transaction_id'):
        payment.sber_transaction_id = provider_response.get('transaction_id')
    payment.full_clean()
    payment.save(update_fields=['status', 'sber_transaction_id', 'updated_at'])
    _log_payment_history(
        payment,
        old_status=old_status,
        new_status=payment.status,
        comment='Выполнен возврат через SmartPay.',
        provider_response=provider_response,
        changed_by=actor,
    )
    return payment


@transaction.atomic
def refund_payment(
    payment: models.ViewingPayment,
    actor,
    amount: Decimal | None = None,
) -> models.ViewingPayment:
    if payment.status != models.ViewingPayment.STATUS_PAID:
        raise ViewingPaymentValidationError('Возврат возможен только для оплаченного платежа.')
    if not payment.sber_order_id:
        raise ViewingPaymentValidationError('У платежа отсутствует invoice_id SmartPay.')

    refund_amount = amount or payment.amount
    try:
        provider_response = refund_invoice(
            invoice_id=payment.sber_order_id,
            amount_kopecks=_amount_to_kopecks(refund_amount.quantize(Decimal('0.01'))),
        )
    except SmartPayError as exc:
        raise SberAcquiringError(str(exc)) from exc

    return mark_payment_refunded(payment, provider_response=provider_response, actor=actor)


def sync_payment_with_sber(payment: models.ViewingPayment, actor=None) -> tuple[models.ViewingPayment, dict[str, Any]]:
    provider_response = fetch_smartpay_status(payment)
    normalized_status = _normalize_provider_status(provider_response.get('invoice_status'))
    if normalized_status == models.ViewingPayment.STATUS_PAID:
        return mark_payment_paid(payment, provider_response, actor=actor), provider_response
    if normalized_status == models.ViewingPayment.STATUS_REFUNDED:
        return mark_payment_refunded(payment, provider_response=provider_response, actor=actor), provider_response
    if normalized_status == models.ViewingPayment.STATUS_FAILED:
        return mark_payment_failed(
            payment,
            provider_response=provider_response,
            actor=actor,
            comment='SmartPay вернул неуспешный статус оплаты.',
        ), provider_response
    if provider_response.get('invoice_url') and payment.payment_url != provider_response.get('invoice_url'):
        payment.payment_url = provider_response.get('invoice_url')
        payment.save(update_fields=['payment_url', 'updated_at'])
    return payment, provider_response
