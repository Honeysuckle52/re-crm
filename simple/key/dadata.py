"""
Клиент сервиса подсказок адресов DaData.

Используется открытый REST-API:
    POST https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address

Авторизация заголовком ``Authorization: Token <api-key>`` согласно
официальной документации https://dadata.ru/api/suggest/address/

Ключ хранится на сервере (settings.DADATA_API_KEY) и в клиентский
JavaScript не попадает — фронтенд ходит в прокси-эндпоинт
/api/dadata/suggest-address/.
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class DadataClient:
    """Тонкая обёртка над API подсказок адресов DaData."""

    def __init__(self, api_url: str | None = None, api_key: str | None = None,
                 timeout: float = 10.0):
        self.api_url = (api_url or settings.DADATA_API_URL).rstrip('/')
        self.api_key = api_key or settings.DADATA_API_KEY
        self.timeout = timeout

    # ------------------------------------------------------------------

    def suggest_address(self, query: str, count: int = 10,
                        locations: list[dict] | None = None) -> list[dict]:
        """
        Получить подсказки адресов по строке поиска.

        :param query: пользовательский ввод (не менее 1 символа).
        :param count: сколько подсказок вернуть (1–20, по умолчанию 10).
        :param locations: фильтры по региону/городу (см. документацию DaData).
        :return: нормализованный список подсказок.
        """
        if not query:
            return []

        payload: dict[str, Any] = {'query': query, 'count': max(1, min(count, 20))}
        if locations:
            payload['locations'] = locations

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'Authorization': f'Token {self.api_key}',
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            logger.error('DaData HTTP-ошибка: %s — %s', exc,
                         getattr(exc.response, 'text', '')[:500])
            raise
        except requests.RequestException as exc:
            logger.error('DaData сетевая ошибка: %s', exc)
            raise

        raw = response.json().get('suggestions', []) or []
        return [self._normalize(item) for item in raw]

    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(item: dict) -> dict:
        """
        Приводим подсказку DaData к удобному для фронтенда/бэкенда виду.

        Возвращаемые ключи намеренно нейтральные (без упоминания ФИАС)
        — хранятся как ``external_id`` в нашей адресной иерархии.
        """
        data = item.get('data') or {}
        lat = data.get('geo_lat')
        lon = data.get('geo_lon')
        return {
            'value': item.get('value') or '',
            'unrestricted_value': item.get('unrestricted_value') or item.get('value') or '',
            'region': data.get('region_with_type') or data.get('region') or '',
            'city': data.get('city_with_type') or data.get('city')
                    or data.get('settlement_with_type') or '',
            'street_type': data.get('street_type') or '',
            'street': data.get('street') or '',
            'house': data.get('house') or '',
            'block': data.get('block') or '',
            'flat': data.get('flat') or '',
            'postal_code': data.get('postal_code') or '',
            'geo_lat': float(lat) if lat else None,
            'geo_lon': float(lon) if lon else None,
            # внутренние идентификаторы DaData (реестр ФНС) — сохраняем
            # под нейтральными именами, чтобы в коде не фигурировал ФИАС.
            'city_external_id': data.get('city_fias_id') or data.get('settlement_fias_id'),
            'street_external_id': data.get('street_fias_id'),
            'house_external_id': data.get('house_fias_id'),
            'address_external_id': data.get('fias_id'),
        }
