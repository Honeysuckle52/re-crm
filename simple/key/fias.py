"""
Клиент для сервиса ФИАС (Федеральная информационная адресная система).

Токен-аутентификация согласно требованиям сервиса ФИАС:
все запросы идут с заголовком ``master-token``, который выдаётся ФНС России
при регистрации сервиса на https://fias.nalog.ru/.

Используется публичный API `fias-public-service.nalog.ru/api/spas/v2.0`.
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class FIASClient:
    """Тонкий обёрточный клиент над REST-API ФИАС."""

    def __init__(self, base_url: str | None = None, token: str | None = None,
                 timeout: float = 10.0):
        self.base_url = (base_url or settings.FIAS_API_URL).rstrip('/')
        self.token = token or settings.FIAS_API_TOKEN
        self.timeout = timeout

    # --- низкоуровневый запрос --------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f'{self.base_url}/{path.lstrip("/")}'
        headers = kwargs.pop('headers', {}) or {}
        headers['master-token'] = self.token
        headers['accept'] = 'application/json'
        try:
            response = requests.request(method, url, headers=headers,
                                        timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            logger.error('FIAS HTTP ошибка: %s — %s', exc, response.text[:500])
            raise
        except requests.RequestException as exc:
            logger.error('FIAS сетевая ошибка: %s', exc)
            raise

    # --- высокоуровневые методы ------------------------------------------

    def search_address(self, query: str, limit: int = 10) -> list[dict]:
        """
        Поиск адреса по строке (автодополнение в UI).

        Возвращает список подсказок с fias_id, полным адресом и иерархией.
        """
        data = self._request('GET', '/GetAddressItemByText',
                             params={'search_string': query, 'limit': limit})
        return data.get('addresses', []) if isinstance(data, dict) else []

    def get_by_fias_id(self, fias_id: str) -> dict | None:
        """Получить адресный объект по Object GUID."""
        data = self._request('GET', '/GetAddressItem',
                             params={'object_id': fias_id})
        return data if isinstance(data, dict) else None

    def get_house(self, house_fias_id: str) -> dict | None:
        """Получить информацию о доме по его FIAS ID."""
        data = self._request('GET', '/GetAddressHierarchyByHouseId',
                             params={'house_id': house_fias_id})
        return data if isinstance(data, dict) else None
