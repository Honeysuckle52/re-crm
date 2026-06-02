"""Pending registration email verification helpers."""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.utils import timezone

from . import mailing

CACHE_PREFIX = 'pending-registration'


def generate_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def _ttl_seconds() -> int:
    minutes = int(getattr(settings, 'EMAIL_VERIFICATION_CODE_TTL_MINUTES', 15) or 15)
    return max(minutes, 1) * 60


def _cache_key(token: str) -> str:
    return f'{CACHE_PREFIX}:{token}'


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def issue_pending_registration(validated_data: dict[str, Any]) -> dict[str, str]:
    code = generate_code()
    token = secrets.token_urlsafe(32)
    data = dict(validated_data)
    password = data.pop('password')
    data.pop('password_confirm', None)
    data['password_hash'] = make_password(password)
    pending_payload = {
        'data': {key: _serialize_value(value) for key, value in data.items()},
        'code_hash': make_password(code),
        'created_at': timezone.now().isoformat(),
    }
    mailing.send_email_verification_code(
        to_email=validated_data['email'],
        code=code,
        client_name=validated_data.get('first_name') or validated_data.get('username') or '',
    )
    cache.set(_cache_key(token), pending_payload, timeout=_ttl_seconds())
    return {'token': token, 'code': code}


def resend_pending_code(token: str) -> bool:
    pending = cache.get(_cache_key(token))
    if not pending:
        return False
    code = generate_code()
    data = pending.get('data') or {}
    mailing.send_email_verification_code(
        to_email=data.get('email', ''),
        code=code,
        client_name=data.get('first_name') or data.get('username') or '',
    )
    pending['code_hash'] = make_password(code)
    cache.set(_cache_key(token), pending, timeout=_ttl_seconds())
    return True


def consume_pending_registration(token: str, code: str) -> dict[str, Any] | None:
    normalized = ''.join(ch for ch in str(code or '') if ch.isdigit())
    if len(normalized) != 6:
        return None
    key = _cache_key(token)
    pending = cache.get(key)
    if not pending or not check_password(normalized, pending.get('code_hash') or ''):
        return None
    cache.delete(key)
    return pending.get('data') or None
