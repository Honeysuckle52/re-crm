# -*- coding: utf-8 -*-
"""HTTP-клиент SmartPay/SmartSber."""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings


class SmartPayError(Exception):
    """Ошибка интеграции со SmartPay."""


def _setting(name: str, default: str = '') -> str:
    return str(getattr(settings, name, default) or '').strip()


def _base_url() -> str:
    base_url = _setting('SMARTPAY_API_BASE_URL')
    if not base_url:
        raise SmartPayError('Не задан SMARTPAY_API_BASE_URL.')
    return base_url if base_url.endswith('/') else f'{base_url}/'


def _token() -> str:
    token = _setting('SMARTPAY_TOKEN')
    if not token:
        raise SmartPayError('Не задан SMARTPAY_TOKEN.')
    return token


def _service_id() -> str:
    service_id = _setting('SMARTPAY_SERVICE_ID')
    if not service_id:
        raise SmartPayError('Не задан SMARTPAY_SERVICE_ID.')
    return service_id


def _timeout() -> int:
    return int(getattr(settings, 'SMARTPAY_TIMEOUT', 15) or 15)


def _create_path() -> str:
    return _setting('SMARTPAY_CREATE_INVOICE_PATH', 'invoices/')


def _status_path(invoice_id: str) -> str:
    template = _setting('SMARTPAY_STATUS_PATH_TEMPLATE', 'invoices/{invoice_id}/')
    return template.format(invoice_id=invoice_id)


def _refund_path(invoice_id: str) -> str:
    template = _setting('SMARTPAY_REFUND_PATH_TEMPLATE', 'invoices/{invoice_id}/refund/')
    return template.format(invoice_id=invoice_id)


def _request(method: str, path: str, *, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = urljoin(_base_url(), path.lstrip('/'))
    headers = {
        'Authorization': f'Bearer {_token()}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json_payload,
                timeout=_timeout(),
            )
            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                raise SmartPayError('SmartPay вернул невалидный JSON.') from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(0.5 * (2 ** attempt))
        except requests.RequestException as exc:
            message = exc.response.text if exc.response is not None else str(exc)
            raise SmartPayError(f'Ошибка запроса к SmartPay: {message}') from exc
    raise SmartPayError(f'SmartPay недоступен: {last_error}') from last_error


def _first_non_empty(payload: dict[str, Any], *keys: str):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ''):
            return value
    return None


def _extract_invoice_id(payload: dict[str, Any]) -> str | None:
    nested = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    value = (
        _first_non_empty(payload, 'invoice_id', 'invoiceId', 'id')
        or _first_non_empty(nested, 'invoice_id', 'invoiceId', 'id')
    )
    return str(value).strip() if value not in (None, '') else None


def _extract_invoice_url(payload: dict[str, Any]) -> str | None:
    nested = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    value = (
        _first_non_empty(payload, 'invoice_url', 'invoiceUrl', 'payment_url', 'paymentUrl', 'url')
        or _first_non_empty(nested, 'invoice_url', 'invoiceUrl', 'payment_url', 'paymentUrl', 'url')
    )
    return str(value).strip() if value not in (None, '') else None


def _extract_status(payload: dict[str, Any]) -> str:
    nested = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    value = (
        _first_non_empty(payload, 'invoice_status', 'invoiceStatus', 'status')
        or _first_non_empty(nested, 'invoice_status', 'invoiceStatus', 'status')
        or 'UNKNOWN'
    )
    return str(value).strip().upper()


def _extract_transaction_id(payload: dict[str, Any]) -> str | None:
    nested = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    value = (
        _first_non_empty(payload, 'transaction_id', 'transactionId', 'payment_id', 'paymentId')
        or _first_non_empty(nested, 'transaction_id', 'transactionId', 'payment_id', 'paymentId')
    )
    return str(value).strip() if value not in (None, '') else None


def create_invoice(
    *,
    viewing_id: int,
    amount_kopecks: int,
    description: str,
    client_email: str | None = None,
    client_phone: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'service_id': _service_id(),
        'invoice_number': f'viewing-{viewing_id}',
        'amount': amount_kopecks,
        'description': description,
    }
    customer: dict[str, Any] = {}
    if client_email:
        customer['email'] = client_email
    if client_phone:
        customer['phone'] = client_phone
    if customer:
        payload['customer'] = customer

    response = _request('POST', _create_path(), json_payload=payload)
    return {
        **response,
        'invoice_id': _extract_invoice_id(response),
        'invoice_url': _extract_invoice_url(response),
        'invoice_status': _extract_status(response),
        'transaction_id': _extract_transaction_id(response),
    }


def get_invoice_status(invoice_id: str) -> dict[str, Any]:
    response = _request('GET', _status_path(invoice_id))
    return {
        **response,
        'invoice_id': _extract_invoice_id(response) or invoice_id,
        'invoice_url': _extract_invoice_url(response),
        'invoice_status': _extract_status(response),
        'transaction_id': _extract_transaction_id(response),
    }


def refund_invoice(*, invoice_id: str, amount_kopecks: int | None = None) -> dict[str, Any]:
    payload = {'service_id': _service_id()}
    if amount_kopecks is not None:
        payload['amount'] = amount_kopecks
    response = _request('POST', _refund_path(invoice_id), json_payload=payload)
    return {
        **response,
        'invoice_id': _extract_invoice_id(response) or invoice_id,
        'invoice_status': _extract_status(response),
        'transaction_id': _extract_transaction_id(response),
    }
