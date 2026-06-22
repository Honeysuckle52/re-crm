# -*- coding: utf-8 -*-
"""Сервис оплаты просмотров объектов через Сбербанк Эквайринг."""
from __future__ import annotations

import logging
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import models

log = logging.getLogger(__name__)

SBER_STATUS_PAID = 2
SBER_STATUS_CREATED = 0
SBER_STATUS_PREAUTHORIZED = 1


class ViewingPaymentError(Exception):
    """Базовая ошибка сервиса оплаты просмотров."""


class ViewingPaymentAccessDenied(ViewingPaymentError):
    """Ошибка прав доступа к оплате просмотра."""


class ViewingPaymentValidationError(ViewingPaymentError):
    """Ошибка бизнес-валидации при работе с оплатой просмотра."""


class SberAcquiringError(ViewingPaymentError):
    """Ошибка взаимодействия с API Сбербанка."""


class SberAcquiringClient:
    def __init__(self):
        base_url = getattr(settings, 'SBER_API_URL', '').strip()
        self.base_url = base_url if base_url.endswith('/') else f'{base_url}/'
        self.username = getattr(settings, 'SBER_USERNAME', '')
        self.password = getattr(settings, 'SBER_PASSWORD', '')
        self.timeout = int(getattr(settings, 'SBER_PAYMENT_TIMEOUT', 10) or 10)

    def _endpoint(self, method: str) -> str:
        return urljoin(self.base_url, method)

    def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.post(
                    self._endpoint(method),
                    data=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                return self._normalize_response(data)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt == 2:
                    break
                time.sleep(0.5 * (2 ** attempt))
            except ValueError as exc:
                raise SberAcquiringError('Сбербанк вернул невалидный JSON.') from exc
            except requests.RequestException as exc:
                raise SberAcquiringError(f'Ошибка запроса к Сбербанку: {exc}') from exc
        raise SberAcquiringError(f'Сбербанк недоступен: {last_error}') from last_error

    @staticmethod
    def _normalize_response(data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data or {})
        normalized['error_code'] = str(normalized.get('errorCode', '') or '')
        normalized['error_message'] = normalized.get('errorMessage') or ''
        status = normalized.get('orderStatus')
        normalized['order_status'] = int(status) if status not in (None, '') else None
        return normalized

    def register_order(
        self,
        *,
        order_number: str,
        amount: Decimal,
        return_url: str,
        fail_url: str,
        description: str,
    ) -> dict[str, Any]:
        return self._request(
            'register.do',
            {
                'userName': self.username,
                'password': self.password,
                'orderNumber': order_number,
                'amount': str(_amount_to_kopecks(amount)),
                'returnUrl': return_url,
                'failUrl': fail_url,
                'description': description,
            },
        )

    def get_order_status_extended(self, order_id: str) -> dict[str, Any]:
        return self._request(
            'getOrderStatusExtended.do',
            {
                'userName': self.username,
                'password': self.password,
                'orderId': order_id,
            },
        )

    def refund(self, *, order_id: str, amount: Decimal) -> dict[str, Any]:
        return self._request(
            'refund.do',
            {
                'userName': self.username,
                'password': self.password,
                'orderId': order_id,
                'amount': str(_amount_to_kopecks(amount)),
            },
        )


def _amount_to_kopecks(amount: Decimal) -> int:
    return int((amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _build_return_url(request, payment_id: int, *, success: bool) -> str:
    path = '/api/viewing-payments/success/' if success else '/api/viewing-payments/fail/'
    return request.build_absolute_uri(f'{path}?payment_id={payment_id}')


def _log_payment_history(
    payment: models.ViewingPayment,
    *,
    old_status: str | None,
    new_status: str,
    comment: str = '',
    sber_response: dict[str, Any] | None = None,
    changed_by=None,
) -> models.PaymentHistory:
    return models.PaymentHistory.objects.create(
        payment=payment,
        old_status=old_status,
        new_status=new_status,
        comment=comment or None,
        sber_response=sber_response or None,
        changed_by=changed_by,
    )


def calculate_viewing_amount(property_obj) -> Decimal:
    property_type = getattr(property_obj, 'premises_type', None) or models.Property.PROPERTY_TYPE_APARTMENT
    amount_map = getattr(settings, 'SBER_VIEWING_AMOUNTS', {}) or {}
    amount = amount_map.get(property_type)
    if amount is None:
        amount = amount_map.get(models.Property.PROPERTY_TYPE_APARTMENT, '500.00')
    return Decimal(str(amount)).quantize(Decimal('0.01'))


@transaction.atomic
def create_viewing_payment(viewing: models.PropertyViewing, actor, request) -> models.ViewingPayment:
    if not actor or not actor.is_authenticated or not actor.is_client:
        raise ViewingPaymentAccessDenied('Оплачивать просмотр может только авторизованный клиент.')
    if viewing.client_profile.user_id != actor.id:
        raise ViewingPaymentAccessDenied('Нельзя оплачивать чужой просмотр.')

    payment = getattr(viewing, 'payment', None)
    if payment and payment.status not in {
        models.ViewingPayment.STATUS_PENDING,
        models.ViewingPayment.STATUS_FAILED,
    }:
        raise ViewingPaymentValidationError('Для этого просмотра уже есть завершённый платёж.')

    amount = calculate_viewing_amount(viewing.property)
    if payment is None:
        payment = models.ViewingPayment(
            viewing=viewing,
            client=actor,
            property=viewing.property,
            amount=amount,
            status=models.ViewingPayment.STATUS_PENDING,
        )
    else:
        payment.amount = amount
        payment.client = actor
        payment.property = viewing.property
        payment.status = models.ViewingPayment.STATUS_PENDING
        payment.paid_at = None
        payment.sber_transaction_id = None
        payment.payment_url = None
    payment.full_clean()
    payment.save()

    response = register_sber_order(payment, request)
    _log_payment_history(
        payment,
        old_status=None if payment.history.count() == 0 else models.ViewingPayment.STATUS_FAILED,
        new_status=payment.status,
        comment='Создание платежа и регистрация заказа в Сбербанке.',
        sber_response=response,
        changed_by=actor,
    )
    return payment


def register_sber_order(payment: models.ViewingPayment, request) -> dict[str, Any]:
    client = SberAcquiringClient()
    if not client.username or not client.password:
        raise ViewingPaymentValidationError('SBER_USERNAME и SBER_PASSWORD должны быть заданы в окружении.')

    order_number = f'VIEW-{payment.viewing_id}-{int(time.time())}'
    response = client.register_order(
        order_number=order_number,
        amount=payment.amount,
        return_url=_build_return_url(request, payment.pk, success=True),
        fail_url=_build_return_url(request, payment.pk, success=False),
        description=f'Оплата просмотра объекта {payment.property.title or payment.property_id}',
    )
    if response.get('error_code') not in {'', '0'}:
        payment.status = models.ViewingPayment.STATUS_FAILED
        payment.save(update_fields=['status', 'updated_at'])
        raise SberAcquiringError(response.get('error_message') or 'Сбербанк не зарегистрировал заказ.')

    payment.sber_order_id = response.get('orderId') or response.get('order_id')
    payment.payment_url = response.get('formUrl') or response.get('payment_url')
    payment.status = models.ViewingPayment.STATUS_PENDING
    payment.full_clean()
    payment.save(update_fields=['sber_order_id', 'payment_url', 'status', 'updated_at'])
    return response


def fetch_sber_order_status(payment: models.ViewingPayment) -> dict[str, Any]:
    if not payment.sber_order_id:
        raise ViewingPaymentValidationError('У платежа отсутствует sber_order_id.')
    client = SberAcquiringClient()
    return client.get_order_status_extended(payment.sber_order_id)


@transaction.atomic
def mark_payment_paid(
    payment: models.ViewingPayment,
    sber_response: dict[str, Any],
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
    payment.sber_transaction_id = (
        sber_response.get('transactionId')
        or sber_response.get('transaction_id')
        or payment.sber_transaction_id
    )
    payment.full_clean()
    payment.save(update_fields=['status', 'paid_at', 'sber_transaction_id', 'updated_at'])

    confirmed_status = models.ViewingStatus.objects.filter(code='confirmed').first()
    if confirmed_status and payment.viewing.status_id != confirmed_status.pk:
        payment.viewing.status = confirmed_status
        payment.viewing.full_clean()
        payment.viewing.save(update_fields=['status'])

    _log_payment_history(
        payment,
        old_status=old_status,
        new_status=payment.status,
        comment='Статус подтверждён по ответу Сбербанка.',
        sber_response=sber_response,
        changed_by=actor,
    )
    return payment


@transaction.atomic
def mark_payment_failed(
    payment: models.ViewingPayment,
    sber_response: dict[str, Any] | None = None,
    actor=None,
    comment: str = '',
) -> models.ViewingPayment:
    payment = models.ViewingPayment.objects.select_for_update().get(pk=payment.pk)
    old_status = payment.status
    payment.status = models.ViewingPayment.STATUS_FAILED
    payment.full_clean()
    payment.save(update_fields=['status', 'updated_at'])
    _log_payment_history(
        payment,
        old_status=old_status,
        new_status=payment.status,
        comment=comment or 'Платёж не был подтверждён.',
        sber_response=sber_response,
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
    refund_amount = (amount or payment.amount).quantize(Decimal('0.01'))
    client = SberAcquiringClient()
    response = client.refund(order_id=payment.sber_order_id or '', amount=refund_amount)
    if response.get('error_code') not in {'', '0'}:
        raise SberAcquiringError(response.get('error_message') or 'Сбербанк не выполнил возврат.')

    old_status = payment.status
    payment.status = models.ViewingPayment.STATUS_REFUNDED
    payment.full_clean()
    payment.save(update_fields=['status', 'updated_at'])
    _log_payment_history(
        payment,
        old_status=old_status,
        new_status=payment.status,
        comment='Возврат средств через Сбербанк.',
        sber_response=response,
        changed_by=actor,
    )
    return payment


def sync_payment_with_sber(payment: models.ViewingPayment, actor=None) -> tuple[models.ViewingPayment, dict[str, Any]]:
    response = fetch_sber_order_status(payment)
    order_status = response.get('order_status')
    if order_status == SBER_STATUS_PAID:
        return mark_payment_paid(payment, response, actor=actor), response
    if order_status in {SBER_STATUS_CREATED, SBER_STATUS_PREAUTHORIZED}:
        return payment, response
    return mark_payment_failed(
        payment,
        sber_response=response,
        actor=actor,
        comment='Сбербанк вернул неуспешный статус платежа.',
    ), response
