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
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Канонический путь до метода подсказок. Если в настройках указан
# только базовый URL — мы сами допишем эндпоинт.
SUGGEST_ADDRESS_PATH = '/suggestions/api/4_1/rs/suggest/address'
SUGGEST_ADDRESS_BASE = 'https://suggestions.dadata.ru'


def _resolve_api_url(raw: str) -> str:
    """
    Привести значение DADATA_API_URL к полному корректному URL.

    Допускаются варианты:
      * полный URL до ``/suggest/address`` — используется как есть;
      * URL вида ``…/rs`` или ``…/4_1`` — дополняем хвостом;
      * пустая строка или ``suggestions.dadata.ru`` — берём значение по умолчанию.
    """
    value = (raw or '').strip().rstrip('/')
    if not value:
        return SUGGEST_ADDRESS_BASE + SUGGEST_ADDRESS_PATH

    # Если уже полный URL на suggest/address — возвращаем как есть.
    if value.endswith('/suggest/address'):
        return value

    # Если передан только хост — склеиваем с каноническим путём.
    if '://' not in value:
        value = 'https://' + value
    if value.rstrip('/') in (
        SUGGEST_ADDRESS_BASE,
        SUGGEST_ADDRESS_BASE + '/suggestions',
        SUGGEST_ADDRESS_BASE + '/suggestions/api',
        SUGGEST_ADDRESS_BASE + '/suggestions/api/4_1',
        SUGGEST_ADDRESS_BASE + '/suggestions/api/4_1/rs',
    ):
        return SUGGEST_ADDRESS_BASE + SUGGEST_ADDRESS_PATH

    # Запасной вариант — дописываем недостающий хвост к тому, что дал пользователь.
    for suffix in ('/suggestions/api/4_1/rs', '/api/4_1/rs', '/4_1/rs', '/rs'):
        if value.endswith(suffix):
            return value + '/suggest/address'

    # Если значение совсем необычное — доверяем пользователю.
    return value


class DadataClient:
    """Тонкая обёртка над API подсказок адресов DaData."""

    def __init__(self, api_url: str | None = None, api_key: str | None = None,
                 timeout: float = 15.0, retries: int = 2):
        self.api_url = _resolve_api_url(api_url or settings.DADATA_API_URL)
        self.api_key = api_key or settings.DADATA_API_KEY
        self.timeout = timeout
        self.retries = max(1, retries)

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
        query = (query or '').strip()
        if not query:
            return []

        payload: dict[str, Any] = {'query': query, 'count': max(1, min(count, 20))}
        if locations:
            payload['locations'] = locations

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Token {self.api_key}',
        }

        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                raw = response.json().get('suggestions', []) or []
                return [self._normalize(item) for item in raw]
            except requests.Timeout as exc:
                last_exc = exc
                logger.warning(
                    'DaData таймаут (попытка %s/%s) URL=%s: %s',
                    attempt, self.retries, self.api_url, exc,
                )
            except requests.HTTPError as exc:
                # 4xx — нет смысла повторять, сразу выбрасываем.
                body = getattr(exc.response, 'text', '') or ''
                logger.error(
                    'DaData HTTP-ошибка %s URL=%s тело=%s',
                    getattr(exc.response, 'status_code', '?'),
                    self.api_url, body[:500],
                )
                raise
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    'DaData сетевая ошибка (попытка %s/%s) URL=%s: %s',
                    attempt, self.retries, self.api_url, exc,
                )

            # Небольшая пауза перед повтором.
            if attempt < self.retries:
                time.sleep(0.3 * attempt)

        # Все попытки исчерпаны.
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(item: dict) -> dict:
        """
        Приводим подсказку DaData к удобному для фронтенда/бэкенда виду.

        Возвращаемые ключи намеренно нейтральные — хранятся как
        ``external_id`` в нашей адресной иерархии.
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
            # внутренние идентификаторы DaData — сохраняем под нейтральными
            # именами, чтобы в коде не фигурировал ФИАС.
            'city_external_id': data.get('city_fias_id') or data.get('settlement_fias_id'),
            'street_external_id': data.get('street_fias_id'),
            'house_external_id': data.get('house_fias_id'),
            'address_external_id': data.get('fias_id'),
        }
