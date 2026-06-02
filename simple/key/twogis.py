"""Клиент 2GIS Places API для обогащения объектов недвижимости данными и фото."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Базовые URL 2GIS API
_PLACES_SEARCH_URL = 'https://catalog.api.2gis.com/3.0/items'
# Static Maps API — доступен с тем же ключом, возвращает спутниковую/схему карты
_STATIC_MAP_URL = 'https://static.maps.2gis.com/1.0'


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

        lat = point.get('lat')
        lon = point.get('lon')
        photos = self._build_static_map_urls(lat=lat, lon=lon) if (lat and lon) else []

        return {
            'name': item.get('name') or '',
            'description': description,
            'address_full': address_full,
            'lat': lat,
            'lon': lon,
            'org_id': org_id,
            'rubric_name': rubric_name,
            'photos': photos,
        }

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    def _build_static_map_urls(
        self,
        *,
        lat: float,
        lon: float,
    ) -> list[str]:
        """Строит набор URL статических карт 2GIS для заданных координат.

        Возвращает три URL с разными масштабами: обзор квартала (zoom 16),
        дом крупно (zoom 18) и схема улицы (zoom 15). Все URL публично
        доступны с тем же API-ключом и не требуют отдельной подписки.
        """
        # Маркер-пин на координатах объекта (формат 2GIS Static Maps: lon,lat)
        marker = f'{lon},{lat}'
        base = f'center={lon},{lat}&size=600x400&markers={marker}&key={self.api_key}'
        return [
            f'{_STATIC_MAP_URL}?{base}&zoom=18',  # дом крупно — маркер на объекте
            f'{_STATIC_MAP_URL}?{base}&zoom=16',  # квартал — видна улица
            f'{_STATIC_MAP_URL}?{base}&zoom=15',  # обзор района
        ]


def apply_property_enrichment(
    property_obj,
    info: dict[str, Any] | None,
    *,
    add_photos: bool = True,
) -> int:
    """Apply 2GIS payload to a property and persist the result."""
    from .models import PropertyPhoto

    if not info:
        return 0

    update_fields: list[str] = []

    def text_or_none(value):
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, list):
            text = ', '.join(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value).strip()
        return text or None

    def set_if_changed(attr: str, value):
        if value is None:
            return
        if getattr(property_obj, attr) != value:
            setattr(property_obj, attr, value)
            update_fields.append(attr)

    set_if_changed('twogis_org_id', text_or_none(info.get('org_id')))
    set_if_changed('twogis_name', text_or_none(info.get('name')))
    set_if_changed('twogis_address_full', text_or_none(info.get('address_full')))
    set_if_changed('twogis_rubric', text_or_none(info.get('rubric_name')))

    lat = info.get('lat')
    lon = info.get('lon')
    if lat is not None:
        lat_value = Decimal(str(lat))
        if property_obj.coordinates_lat != lat_value:
            property_obj.coordinates_lat = lat_value
            update_fields.append('coordinates_lat')
    if lon is not None:
        lon_value = Decimal(str(lon))
        if property_obj.coordinates_lon != lon_value:
            property_obj.coordinates_lon = lon_value
            update_fields.append('coordinates_lon')

    twogis_desc = text_or_none(info.get('description')) or ''
    if twogis_desc:
        existing_description = (property_obj.description or '').strip()
        if not existing_description:
            property_obj.description = twogis_desc
            update_fields.append('description')
        elif not existing_description.startswith(twogis_desc):
            property_obj.description = f'{twogis_desc}\n\n{existing_description}'
            update_fields.append('description')

    set_if_changed('twogis_synced_at', timezone.now())

    if update_fields:
        property_obj.save(update_fields=list(dict.fromkeys(update_fields)))

    if not add_photos or PropertyPhoto.objects.filter(property=property_obj).exists():
        return 0

    photo_urls: list[str] = info.get('photos') or []
    if not photo_urls:
        return 0

    for order, url in enumerate(photo_urls):
        PropertyPhoto.objects.create(
            property=property_obj,
            url=url,
            caption='2GIS',
            is_cover=(order == 0),
            order=order,
        )
    return len(photo_urls)
