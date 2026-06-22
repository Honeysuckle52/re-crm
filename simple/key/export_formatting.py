# -*- coding: utf-8 -*-
"""Unified CSV/XLSX/JSON export formatting helpers."""
from __future__ import annotations

import csv
import io
import json
import re
from collections import OrderedDict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Iterable

from django.utils import timezone


FILENAME_SAFE_RE = re.compile(r'[^\w.@+-]+', re.UNICODE)
DATE_FORMAT = '%d.%m.%Y %H:%M:%S'


EXPORT_COLUMN_LABELS = {
    'id': 'Идентификатор',
    'pk': 'Идентификатор',
    'title': 'Название',
    'name': 'Название',
    'code': 'Код',
    'description': 'Описание',
    'created_at': 'Дата создания',
    'updated_at': 'Дата обновления',
    'closed_at': 'Дата закрытия',
    'operation_type': 'Тип операции',
    'operation_type_code': 'Код типа операции',
    'operation_type_name': 'Тип операции',
    'status': 'Статус',
    'status_code': 'Код статуса',
    'status_name': 'Статус',
    'city': 'Город',
    'region': 'Регион',
    'street': 'Улица',
    'street_type': 'Тип улицы',
    'house': 'Дом',
    'flat': 'Квартира',
    'postal_code': 'Почтовый индекс',
    'address': 'Адрес',
    'address_preferences': 'Пожелания по адресу',
    'price': 'Цена',
    'price_final': 'Итоговая цена',
    'price_per_sqm': 'Цена за м2',
    'min_price': 'Минимальная цена',
    'max_price': 'Максимальная цена',
    'area_total': 'Общая площадь',
    'min_area': 'Минимальная площадь',
    'max_area': 'Максимальная площадь',
    'rooms_count': 'Количество комнат',
    'floor_number': 'Этаж',
    'total_floors': 'Всего этажей',
    'premises_type': 'Тип помещения',
    'property_type': 'Тип помещения',
    'property': 'Объект',
    'property_id': 'Идентификатор объекта',
    'property_title': 'Объект',
    'owner': 'Владелец',
    'owner_username': 'Владелец',
    'owner_email': 'Email владельца',
    'owner_phone': 'Телефон владельца',
    'client': 'Клиент',
    'client_username': 'Клиент',
    'client_email': 'Email клиента',
    'client_phone': 'Телефон клиента',
    'agent': 'Агент',
    'agent_username': 'Агент',
    'assignee': 'Исполнитель',
    'assignee_username': 'Исполнитель',
    'created_by': 'Создатель',
    'created_by_username': 'Создатель',
    'username': 'Логин',
    'email': 'Email',
    'phone': 'Телефон',
    'user_type': 'Код типа пользователя',
    'user_type_display': 'Тип пользователя',
    'role_code': 'Код роли',
    'role_name': 'Роль',
    'is_active': 'Активен',
    'is_staff': 'Сотрудник',
    'is_superuser': 'Администратор',
    'is_email_verified': 'Email подтвержден',
    'is_phone_verified': 'Телефон подтвержден',
    'deal': 'Сделка',
    'deal_id': 'Идентификатор сделки',
    'deal_number': 'Номер сделки',
    'deal_date': 'Дата сделки',
    'request': 'Заявка',
    'request_id': 'Идентификатор заявки',
    'request_label': 'Заявка',
    'task': 'Задача',
    'task_type': 'Тип задач',
    'task_type_display': 'Тип задачи',
    'priority': 'Приоритет',
    'priority_display': 'Приоритет',
    'due_date': 'Срок',
    'completed_at': 'Закрыта',
    'is_auto_closed': 'Закрыта автоматически',
    'result': 'Результат',
    'result_summary': 'Результат',
    'commission_percent': 'Процент комиссии',
    'commission_amount': 'Сумма комиссии',
    'contract_status': 'Код статуса договора',
    'contract_status_display': 'Статус договора',
    'contract_requested_at': 'Дата запроса договора',
    'contract_generated_at': 'Дата формирования договора',
    'notes': 'Примечания',
    'ordering': 'Сортировка',
    'report_code': 'Код отчета',
    'dictionary': 'Справочник',
    'order': 'Порядок',
    'max_active_tasks': 'Максимум активных задач',
    'max_in_progress_tasks': 'Максимум задач в работе',
    'max_active_requests': 'Максимум активных заявок',
    'entity_type': 'Код типа сущности',
    'entity_type_display': 'Тип сущности',
    'entity_id': 'Идентификатор сущности',
    'action_code': 'Код действия',
    'action_label': 'Действие',
    'message': 'Сообщение',
    'metadata': 'Метаданные',
}

TOKEN_LABELS = {
    'id': 'идентификатор',
    'code': 'код',
    'name': 'название',
    'title': 'название',
    'date': 'дата',
    'created': 'создания',
    'updated': 'обновления',
    'closed': 'закрытия',
    'completed': 'закрыта',
    'status': 'статус',
    'type': 'тип',
    'display': 'отображение',
    'client': 'клиент',
    'agent': 'агент',
    'assignee': 'исполнитель',
    'owner': 'владелец',
    'property': 'объект',
    'request': 'заявка',
    'deal': 'сделка',
    'task': 'задача',
    'price': 'цена',
    'area': 'площадь',
    'min': 'минимальная',
    'max': 'максимальная',
    'total': 'общая',
    'final': 'итоговая',
    'amount': 'сумма',
    'percent': 'процент',
    'email': 'email',
    'phone': 'телефон',
    'username': 'логин',
    'description': 'описание',
    'notes': 'примечания',
}


def export_timestamp(now=None) -> datetime:
    value = now or timezone.now()
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value)


def build_export_filename(action: str, user, extension: str, *, generated_at=None) -> str:
    username = getattr(user, 'username', None) or 'user'
    safe_username = FILENAME_SAFE_RE.sub('_', str(username).strip()).strip('._-')
    safe_action = FILENAME_SAFE_RE.sub('_', str(action or 'export').strip()).strip('._-')
    stamp = export_timestamp(generated_at).strftime('%Y-%m-%d_%H-%M-%S')
    return f'{safe_action or "export"}_{safe_username or "user"}_{stamp}.{extension}'


def is_empty_export_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip() or value.strip().lower() == 'null'
    if isinstance(value, dict):
        return not any(not is_empty_export_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return not any(not is_empty_export_value(item) for item in value)
    return False


def normalize_export_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.replace(microsecond=0).strftime(DATE_FORMAT)
    if isinstance(value, date):
        return datetime.combine(value, time.min).strftime(DATE_FORMAT)
    if isinstance(value, dict):
        return {
            str(key): normalize_export_value(item)
            for key, item in value.items()
            if not is_empty_export_value(item)
        }
    if isinstance(value, (list, tuple, set)):
        return [
            normalize_export_value(item)
            for item in value
            if not is_empty_export_value(item)
        ]
    return value


def _looks_like_identifier(value: str) -> bool:
    return bool(re.fullmatch(r'[A-Za-z0-9_]+', value or ''))


def _fallback_label(key: str) -> str:
    parts = [part for part in re.split(r'[_\s]+', str(key)) if part]
    translated = [TOKEN_LABELS.get(part.lower()) for part in parts]
    if translated and all(translated):
        label = ' '.join(translated)
        return label[:1].upper() + label[1:]
    return str(key)


def _label_for_key(key: str, labels: dict[str, str] | None) -> str:
    provided = (labels or {}).get(key)
    if provided and not _looks_like_identifier(provided):
        return provided
    if not _looks_like_identifier(key):
        return key
    return EXPORT_COLUMN_LABELS.get(key) or _fallback_label(key)


def _ordered_keys(row: dict, columns: Iterable[tuple[str, str]] | None) -> list[str]:
    ordered: list[str] = []
    if columns:
        ordered.extend(key for key, _ in columns if key in row)
    ordered.extend(key for key in row if key not in ordered)
    return ordered


def _clean_mapping(row: dict, labels: dict[str, str] | None, columns=None) -> OrderedDict:
    cleaned = OrderedDict()
    used_labels: set[str] = set()
    for key in _ordered_keys(row, columns):
        value = row.get(key)
        if is_empty_export_value(value):
            continue
        label = _label_for_key(str(key), labels)
        if label in used_labels:
            continue
        used_labels.add(label)
        normalized = normalize_export_value(value)
        if is_empty_export_value(normalized):
            continue
        cleaned[label] = normalized
    return cleaned


def cleaned_export_rows(
    data: list[dict],
    *,
    columns: Iterable[tuple[str, str]] | None = None,
) -> list[OrderedDict]:
    labels = {key: label for key, label in (columns or [])}
    result: list[OrderedDict] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        cleaned = _clean_mapping(row, labels, columns)
        if cleaned:
            result.append(cleaned)
    return result


def _flatten_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _table_headers(rows: list[OrderedDict]) -> list[str]:
    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers


def formatted_export_rows(
    data: list[dict],
    *,
    columns: Iterable[tuple[str, str]] | None = None,
) -> list[list[object]]:
    cleaned_rows = cleaned_export_rows(data, columns=columns)
    if not cleaned_rows:
        return []
    headers = _table_headers(cleaned_rows)
    return [
        headers,
        *[
            [_flatten_value(row.get(header, '')) for header in headers]
            for row in cleaned_rows
        ],
    ]


def _csv_bytes(rows: list[list[object]]) -> bytes:
    buffer = io.BytesIO()
    wrapper = io.TextIOWrapper(buffer, encoding='utf-8-sig', newline='')
    writer = csv.writer(wrapper, delimiter=';')
    writer.writerows(rows)
    wrapper.flush()
    return buffer.getvalue()


def _metadata_rows(title: str | None, metadata: dict | None) -> list[list[object]]:
    rows: list[list[object]] = []
    if title:
        rows.append([title])
        rows.append([])
    if metadata:
        for key, value in _clean_mapping(metadata, None).items():
            rows.append([key, _flatten_value(value)])
        rows.append([])
    return rows


def format_export_data(
    data: list[dict],
    fmt: str,
    *,
    columns: Iterable[tuple[str, str]] | None = None,
    title: str | None = None,
    metadata: dict | None = None,
    generated_at=None,
):
    """Return formatted CSV bytes, JSON text or XLSX-ready rows."""
    normalized = (fmt or '').strip().lower()
    cleaned_rows = cleaned_export_rows(data, columns=columns)

    if normalized == 'json':
        payload = {
            'title': title or '',
            'summary': _clean_mapping(metadata or {}, None),
            'rows': cleaned_rows,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    rows = formatted_export_rows(data, columns=columns)
    if normalized == 'xlsx':
        return [*_metadata_rows(title, metadata), *rows]
    if normalized == 'csv':
        return _csv_bytes([*_metadata_rows(title, metadata), *rows])
    raise ValueError('Unsupported export format.')
