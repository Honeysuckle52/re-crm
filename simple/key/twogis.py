"""Клиент 2GIS Places API для обогащения объектов недвижимости данными и фото."""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Базовые URL 2GIS Places API
_PLACES_SEARCH_URL = 'https://catalog.api.2gis.com/3.0/items'
_PHOTOS_URL = 'https://api.photo.2gis.com/2.0/photo'


class TwoGisClient:
    """Тонкая обёртка над 2GIS Places API.

    Используется только на серверной стороне при заполнении базы данных
    (seed_data). Ключ берётся из настройки ``TWOGIS_API_KEY`` (settings.py /
    .env) и никогда не передаётся в браузер.
    """

    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        self.api_key = api_key or getattr(settings, 'TWOGIS_API_KEY', '')
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    def search_by_address(self, address: str, *, city: str = '') -> dict[str, Any] | None:
        """Ищет организацию / здание по адресу и возвращает первый результат.

        Возвращаемый словарь содержит поля:
        - ``name`` — название объекта
        - ``description`` — краткое описание (purpose_name / rubric / …)
        - ``address_full`` — полный адрес из 2GIS
        - ``lat`` / ``lon`` — координаты
        - ``org_id`` — идентификатор для запроса фото
        - ``photos`` — список URL фотографий (может быть пустым)
        """
        if not self.api_key:
            return None

        query = f'{city} {address}'.strip() if city else address
        try:
            resp = requests.get(
                _PLACES_SEARCH_URL,
                params={
                    'q': query,
                    'key': self.api_key,
                    'fields': 'items.point,items.rubrics,items.address,items.description',
                    'page_size': 1,
                    'type': 'building,branch',
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning('2GIS search_by_address ошибка (q=%r): %s', query, exc)
            return None

        data = resp.json()
        items = (data.get('result') or {}).get('items') or []
        if not items:
            return None

        item = items[0]
        org_id = item.get('id') or ''
        point = item.get('point') or {}
        rubrics = item.get('rubrics') or []
        rubric_name = rubrics[0].get('name', '') if rubrics else ''
        address_obj = item.get('address') or {}
        address_full = address_obj.get('name') or address_obj.get('components') or query

        description = (
            item.get('description')
            or rubric_name
            or ''
        )

        photos = self._fetch_photos(org_id) if org_id else []

        return {
            'name': item.get('name') or '',
            'description': description,
            'address_full': address_full,
            'lat': point.get('lat'),
            'lon': point.get('lon'),
            'org_id': org_id,
            'photos': photos,
        }

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _fetch_photos(self, obj_id: str, *, limit: int = 5) -> list[str]:
        """Возвращает список URL фотографий для объекта 2GIS."""
        if not obj_id:
            return []
        try:
            resp = requests.get(
                _PHOTOS_URL,
                params={
                    'object_id': obj_id,
                    'key': self.api_key,
                    'page_size': limit,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.debug('2GIS _fetch_photos ошибка (obj_id=%r): %s', obj_id, exc)
            return []

        data = resp.json()
        items = (data.get('result') or {}).get('items') or []
        urls: list[str] = []
        for photo in items:
            previews = photo.get('previews') or []
            if previews:
                # Берём наибольший доступный превью
                biggest = max(previews, key=lambda p: p.get('width', 0), default=None)
                if biggest and biggest.get('url'):
                    urls.append(biggest['url'])
        return urls
