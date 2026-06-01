"""Импорт и экспорт данных CRM."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import audit as audit_service
from . import models, serializers
from .xlsx_utils import WorkbookSheet, build_xlsx_bytes, load_xlsx_rows


PROPERTY_EXPORT_COLUMNS = (
    ('id', 'id'),
    ('title', 'title'),
    ('operation_type_code', 'operation_type_code'),
    ('status_code', 'status_code'),
    ('city', 'city'),
    ('region', 'region'),
    ('street', 'street'),
    ('street_type', 'street_type'),
    ('house', 'house'),
    ('block', 'block'),
    ('flat', 'flat'),
    ('postal_code', 'postal_code'),
    ('price', 'price'),
    ('area_total', 'area_total'),
    ('rooms_count', 'rooms_count'),
    ('floor_number', 'floor_number'),
    ('total_floors', 'total_floors'),
    ('description', 'description'),
)

PROPERTY_REQUIRED_COLUMNS = (
    'operation_type_code',
    'status_code',
    'city',
    'street',
    'house',
    'price',
)


@dataclass(frozen=True)
class DictionaryDefinition:
    code: str
    title: str
    queryset: object
    columns: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TabularExportDefinition:
    filename_prefix: str
    sheet_title: str
    columns: tuple[tuple[str, str], ...]


DICTIONARY_DEFINITIONS = (
    DictionaryDefinition(
        code='operation_types',
        title='Типы операций',
        queryset=models.OperationType.objects.order_by('name'),
        columns=(
            ('id', 'id'),
            ('code', 'code'),
            ('name', 'name'),
        ),
    ),
    DictionaryDefinition(
        code='property_statuses',
        title='Статусы объектов',
        queryset=models.PropertyStatus.objects.order_by('name'),
        columns=(
            ('id', 'id'),
            ('code', 'code'),
            ('name', 'name'),
        ),
    ),
    DictionaryDefinition(
        code='request_statuses',
        title='Статусы заявок',
        queryset=models.RequestStatus.objects.order_by('name'),
        columns=(
            ('id', 'id'),
            ('code', 'code'),
            ('name', 'name'),
        ),
    ),
    DictionaryDefinition(
        code='deal_statuses',
        title='Статусы сделок',
        queryset=models.DealStatus.objects.order_by('order', 'name'),
        columns=(
            ('id', 'id'),
            ('code', 'code'),
            ('name', 'name'),
            ('order', 'order'),
        ),
    ),
    DictionaryDefinition(
        code='task_statuses',
        title='Статусы задач',
        queryset=models.TaskStatus.objects.order_by('order', 'name'),
        columns=(
            ('id', 'id'),
            ('code', 'code'),
            ('name', 'name'),
            ('order', 'order'),
        ),
    ),
    DictionaryDefinition(
        code='user_roles',
        title='Роли пользователей',
        queryset=models.UserRole.objects.order_by('name'),
        columns=(
            ('id', 'id'),
            ('code', 'code'),
            ('name', 'name'),
            ('description', 'description'),
            ('max_active_tasks', 'max_active_tasks'),
            ('max_in_progress_tasks', 'max_in_progress_tasks'),
            ('max_active_requests', 'max_active_requests'),
        ),
    ),
)


PROPERTY_EXPORT_DEFINITION = TabularExportDefinition(
    filename_prefix='properties',
    sheet_title='Объекты',
    columns=PROPERTY_EXPORT_COLUMNS,
)

REQUEST_EXPORT_COLUMNS = (
    ('id', 'id'),
    ('client_username', 'client_username'),
    ('client_email', 'client_email'),
    ('client_phone', 'client_phone'),
    ('agent_username', 'agent_username'),
    ('property_id', 'property_id'),
    ('property_title', 'property_title'),
    ('operation_type_code', 'operation_type_code'),
    ('status_code', 'status_code'),
    ('status_name', 'status_name'),
    ('property_type', 'property_type'),
    ('min_price', 'min_price'),
    ('max_price', 'max_price'),
    ('min_area', 'min_area'),
    ('max_area', 'max_area'),
    ('rooms_count', 'rooms_count'),
    ('address_preferences', 'address_preferences'),
    ('description', 'description'),
    ('created_at', 'created_at'),
    ('updated_at', 'updated_at'),
    ('closed_at', 'closed_at'),
)

REQUEST_EXPORT_DEFINITION = TabularExportDefinition(
    filename_prefix='requests',
    sheet_title='Заявки',
    columns=REQUEST_EXPORT_COLUMNS,
)

TASK_EXPORT_COLUMNS = (
    ('id', 'id'),
    ('title', 'title'),
    ('task_type', 'task_type'),
    ('task_type_display', 'task_type_display'),
    ('priority', 'priority'),
    ('priority_display', 'priority_display'),
    ('status_code', 'status_code'),
    ('status_name', 'status_name'),
    ('assignee_username', 'assignee_username'),
    ('created_by_username', 'created_by_username'),
    ('client_username', 'client_username'),
    ('property_id', 'property_id'),
    ('property_title', 'property_title'),
    ('request_id', 'request_id'),
    ('deal_id', 'deal_id'),
    ('due_date', 'due_date'),
    ('completed_at', 'completed_at'),
    ('is_auto_closed', 'is_auto_closed'),
    ('result', 'result'),
    ('created_at', 'created_at'),
    ('updated_at', 'updated_at'),
)

TASK_EXPORT_DEFINITION = TabularExportDefinition(
    filename_prefix='tasks',
    sheet_title='Задачи',
    columns=TASK_EXPORT_COLUMNS,
)

DEAL_EXPORT_COLUMNS = (
    ('id', 'id'),
    ('deal_number', 'deal_number'),
    ('request_id', 'request_id'),
    ('property_id', 'property_id'),
    ('property_title', 'property_title'),
    ('agent_username', 'agent_username'),
    ('client_username', 'client_username'),
    ('operation_type_code', 'operation_type_code'),
    ('operation_type_name', 'operation_type_name'),
    ('status_code', 'status_code'),
    ('status_name', 'status_name'),
    ('price_final', 'price_final'),
    ('commission_percent', 'commission_percent'),
    ('commission_amount', 'commission_amount'),
    ('deal_date', 'deal_date'),
    ('contract_status', 'contract_status'),
    ('contract_status_display', 'contract_status_display'),
    ('contract_requested_at', 'contract_requested_at'),
    ('contract_generated_at', 'contract_generated_at'),
    ('notes', 'notes'),
)

DEAL_EXPORT_DEFINITION = TabularExportDefinition(
    filename_prefix='deals',
    sheet_title='Сделки',
    columns=DEAL_EXPORT_COLUMNS,
)

USER_EXPORT_COLUMNS = (
    ('id', 'id'),
    ('username', 'username'),
    ('email', 'email'),
    ('phone', 'phone'),
    ('user_type', 'user_type'),
    ('user_type_display', 'user_type_display'),
    ('role_code', 'role_code'),
    ('role_name', 'role_name'),
    ('is_active', 'is_active'),
    ('is_staff', 'is_staff'),
    ('is_superuser', 'is_superuser'),
    ('is_email_verified', 'is_email_verified'),
    ('is_phone_verified', 'is_phone_verified'),
    ('created_at', 'created_at'),
)

USER_EXPORT_DEFINITION = TabularExportDefinition(
    filename_prefix='users',
    sheet_title='Пользователи',
    columns=USER_EXPORT_COLUMNS,
)


def _validate_property_headers(headers: list[str]) -> None:
    missing_headers = [
        column for column in PROPERTY_REQUIRED_COLUMNS
        if column not in headers
    ]
    if missing_headers:
        raise ValidationError({
            'file': [
                'В файле отсутствуют обязательные колонки: '
                + ', '.join(missing_headers) + '.',
            ],
        })


def _decode_uploaded_text(upload) -> str:
    raw = upload.read()
    upload.seek(0)
    for encoding in ('utf-8-sig', 'utf-8', 'cp1251'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError({
        'file': ['Файл должен быть сохранён в UTF-8 или Windows-1251.'],
    })


def _parse_decimal(raw: str, *, field: str, row_number: int) -> Decimal | None:
    text = (raw or '').strip()
    if not text:
        return None
    normalized = text.replace(' ', '').replace(',', '.')
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValidationError({
            field: [f'Строка {row_number}: поле "{field}" должно быть числом.'],
        }) from exc


def _parse_int(raw: str, *, field: str, row_number: int) -> int | None:
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValidationError({
            field: [f'Строка {row_number}: поле "{field}" должно быть целым числом.'],
        }) from exc


def _required_value(row: dict, *, key: str, row_number: int) -> str:
    value = (row.get(key) or '').strip()
    if value:
        return value
    raise ValidationError({
        key: [f'Строка {row_number}: поле "{key}" обязательно.'],
    })


def _property_payload_from_row(
    row: dict,
    *,
    row_number: int,
    operation_type_ids: dict[str, int],
    status_ids: dict[str, int],
) -> tuple[dict, int | None]:
    operation_type_code = _required_value(
        row, key='operation_type_code', row_number=row_number,
    )
    status_code = _required_value(
        row, key='status_code', row_number=row_number,
    )
    city = _required_value(row, key='city', row_number=row_number)
    street = _required_value(row, key='street', row_number=row_number)
    house = _required_value(row, key='house', row_number=row_number)
    price = _parse_decimal(
        _required_value(row, key='price', row_number=row_number),
        field='price',
        row_number=row_number,
    )
    assert price is not None

    operation_type_id = operation_type_ids.get(operation_type_code)
    if operation_type_id is None:
        raise ValidationError({
            'operation_type_code': [
                f'Строка {row_number}: неизвестный код операции "{operation_type_code}".',
            ],
        })

    status_id = status_ids.get(status_code)
    if status_id is None:
        raise ValidationError({
            'status_code': [
                f'Строка {row_number}: неизвестный код статуса "{status_code}".',
            ],
        })

    property_id = _parse_int(
        row.get('id', ''),
        field='id',
        row_number=row_number,
    )

    address_data = {
        'value': ', '.join(
            part for part in (
                (row.get('region') or '').strip(),
                city,
                f"{(row.get('street_type') or '').strip()} {street}".strip(),
                f"д. {house}",
                (
                    f"к. {(row.get('block') or '').strip()}"
                    if (row.get('block') or '').strip() else ''
                ),
                (
                    f"кв. {(row.get('flat') or '').strip()}"
                    if (row.get('flat') or '').strip() else ''
                ),
            ) if part
        ),
        'region': (row.get('region') or '').strip(),
        'city': city,
        'street': street,
        'street_type': (row.get('street_type') or '').strip(),
        'house': house,
        'block': (row.get('block') or '').strip(),
        'flat': (row.get('flat') or '').strip(),
        'postal_code': (row.get('postal_code') or '').strip(),
    }

    payload = {
        'title': (row.get('title') or '').strip() or None,
        'operation_type': operation_type_id,
        'status': status_id,
        'address_data': address_data,
        'price': float(price),
        'area_total': _parse_decimal(
            row.get('area_total', ''),
            field='area_total',
            row_number=row_number,
        ),
        'rooms_count': _parse_int(
            row.get('rooms_count', ''),
            field='rooms_count',
            row_number=row_number,
        ),
        'floor_number': _parse_int(
            row.get('floor_number', ''),
            field='floor_number',
            row_number=row_number,
        ),
        'total_floors': _parse_int(
            row.get('total_floors', ''),
            field='total_floors',
            row_number=row_number,
        ),
        'description': (row.get('description') or '').strip() or '',
    }
    return payload, property_id


def _csv_property_rows(upload) -> tuple[list[str], list[tuple[int, dict]]]:
    content = _decode_uploaded_text(upload)
    reader = csv.DictReader(io.StringIO(content), delimiter=';')
    if not reader.fieldnames:
        raise ValidationError({'file': ['CSV-файл пустой или не содержит заголовка.']})

    headers = [header.strip() for header in reader.fieldnames if header and header.strip()]
    _validate_property_headers(headers)

    rows: list[tuple[int, dict]] = []
    for row_number, row in enumerate(reader, start=2):
        if not any((value or '').strip() for value in row.values()):
            continue
        rows.append((row_number, row))
    return headers, rows


def _xlsx_property_rows(upload) -> tuple[list[str], list[tuple[int, dict]]]:
    sheet_rows = load_xlsx_rows(upload)
    if not sheet_rows:
        raise ValidationError({'file': ['XLSX-файл пустой или не содержит строк.']})

    raw_headers = [
        (value or '').strip()
        for value in sheet_rows[0]
    ]
    headers = [header for header in raw_headers if header]
    if not headers:
        raise ValidationError({'file': ['В XLSX не найдены заголовки колонок.']})
    _validate_property_headers(headers)

    rows: list[tuple[int, dict]] = []
    for row_number, values in enumerate(sheet_rows[1:], start=2):
        row = {
            header: (values[index].strip() if index < len(values) else '')
            for index, header in enumerate(raw_headers)
            if header
        }
        if not any(value.strip() for value in row.values()):
            continue
        rows.append((row_number, row))
    return headers, rows


def _import_properties_rows(
    rows: list[tuple[int, dict]],
    *,
    actor,
    request=None,
    source_code: str,
    source_label: str,
) -> dict:
    operation_type_ids = {
        item.code: item.pk
        for item in models.OperationType.objects.all()
    }
    status_ids = {
        item.code: item.pk
        for item in models.PropertyStatus.objects.all()
    }

    prepared_rows: list[tuple[serializers.PropertySerializer, int | None]] = []
    created_count = 0
    updated_count = 0

    for row_number, row in rows:
        payload, property_id = _property_payload_from_row(
            row,
            row_number=row_number,
            operation_type_ids=operation_type_ids,
            status_ids=status_ids,
        )
        instance = None
        if property_id is not None:
            instance = models.Property.objects.filter(pk=property_id).first()
            if instance is None:
                raise ValidationError({
                    'id': [f'Строка {row_number}: объект с id={property_id} не найден.'],
                })
        serializer = serializers.PropertySerializer(
            instance=instance,
            data=payload,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        prepared_rows.append((serializer, property_id))
        if instance is None:
            created_count += 1
        else:
            updated_count += 1

    if not prepared_rows:
        raise ValidationError({'file': ['В файле нет строк для импорта.']})

    for serializer, property_id in prepared_rows:
        property_obj = serializer.save()
        if property_id is None:
            audit_service.log_event(
                entity=property_obj,
                action_code='import_created',
                action_label='Импорт объекта',
                actor=actor,
                message=f'Объект недвижимости создан импортом из {source_label}.',
                metadata={'source': source_code},
            )
        else:
            audit_service.log_event(
                entity=property_obj,
                action_code='import_updated',
                action_label='Импорт обновления объекта',
                actor=actor,
                message=f'Карточка объекта обновлена импортом из {source_label}.',
                metadata={
                    'source': source_code,
                    'changed_fields': sorted(serializer.validated_data.keys()),
                },
            )

    return {
        'processed_rows': len(prepared_rows),
        'created': created_count,
        'updated': updated_count,
        'imported_at': timezone.now(),
        'actor_id': getattr(actor, 'pk', None),
        'source': source_code,
    }


def import_properties(upload, *, actor, request=None) -> dict:
    filename = (getattr(upload, 'name', '') or '').lower()
    if filename.endswith('.xlsx'):
        _, rows = _xlsx_property_rows(upload)
        return _import_properties_rows(
            rows,
            actor=actor,
            request=request,
            source_code='xlsx_import',
            source_label='XLSX',
        )
    _, rows = _csv_property_rows(upload)
    return _import_properties_rows(
        rows,
        actor=actor,
        request=request,
        source_code='csv_import',
        source_label='CSV',
    )


def _property_export_rows(queryset) -> list[dict]:
    rows: list[dict] = []
    for property_obj in queryset.select_related(
        'operation_type', 'status', 'address__house__street__city',
    ):
        address = property_obj.address
        house = address.house
        street = house.street
        city = street.city
        rows.append({
            'id': property_obj.pk,
            'title': property_obj.title or '',
            'operation_type_code': getattr(property_obj.operation_type, 'code', ''),
            'status_code': getattr(property_obj.status, 'code', ''),
            'city': city.name,
            'region': city.region or '',
            'street': street.name,
            'street_type': street.street_type or '',
            'house': house.house_number,
            'block': house.building or '',
            'flat': address.apartment_number or '',
            'postal_code': house.postal_code or '',
            'price': property_obj.price,
            'area_total': str(property_obj.area_total) if property_obj.area_total is not None else '',
            'rooms_count': property_obj.rooms_count or '',
            'floor_number': property_obj.floor_number or '',
            'total_floors': property_obj.total_floors or '',
            'description': property_obj.description or '',
        })
    return rows


def _xlsx_response(filename: str, sheets: list[WorkbookSheet]) -> HttpResponse:
    response = HttpResponse(
        build_xlsx_bytes(sheets),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _export_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _export_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_export_json_value(item) for item in value]
    return value


def _export_cell_value(value):
    value = _export_json_value(value)
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _normalized_export_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            key: _export_json_value(value)
            for key, value in row.items()
        }
        for row in rows
    ]


def _export_user_label(user) -> str:
    if user is None:
        return 'Пользователь'
    parts = [
        getattr(user, 'last_name', ''),
        getattr(user, 'first_name', ''),
        getattr(user, 'middle_name', ''),
    ]
    full_name = ' '.join(part for part in parts if part).strip()
    if full_name:
        return full_name
    return getattr(user, 'username', None) or getattr(user, 'email', None) or 'Пользователь'


def _export_title(definition: TabularExportDefinition, user) -> str:
    stamp = timezone.localtime(timezone.now()).strftime('%d.%m.%Y %H:%M')
    return f'{definition.sheet_title} · Сформировал: {_export_user_label(user)} · {stamp}'


def _export_tabular(
    definition: TabularExportDefinition,
    rows: list[dict],
    fmt: str,
    *,
    title: str | None = None,
) -> HttpResponse:
    normalized = (fmt or '').strip().lower()
    suffix = timezone.localdate().strftime('%Y%m%d')
    prepared_rows = _normalized_export_rows(rows)
    report_title = title

    if normalized == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="{definition.filename_prefix}-{suffix}.csv"'
        )
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        if report_title:
            writer.writerow([report_title])
            writer.writerow([])
        writer.writerow([label for _, label in definition.columns])
        for row in prepared_rows:
            writer.writerow([
                _export_cell_value(row.get(key))
                for key, _ in definition.columns
            ])
        return response

    if normalized == 'json':
        response = HttpResponse(
            content_type='application/json; charset=utf-8',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="{definition.filename_prefix}-{suffix}.json"'
        )
        payload = {
            'exported_at': timezone.now().isoformat(),
            'count': len(prepared_rows),
            'items': prepared_rows,
        }
        if report_title:
            payload['title'] = report_title
        response.write(json.dumps(payload, ensure_ascii=False, indent=2))
        return response

    if normalized == 'xlsx':
        rows_payload = [
            [label for _, label in definition.columns],
            *[
                [
                    _export_cell_value(row.get(key))
                    for key, _ in definition.columns
                ]
                for row in prepared_rows
            ],
        ]
        if report_title:
            rows_payload = [[report_title], [], *rows_payload]
        return _xlsx_response(
            f'{definition.filename_prefix}-{suffix}.xlsx',
            [
                WorkbookSheet.from_rows(
                    definition.sheet_title,
                    rows_payload,
                ),
            ],
        )

    raise ValidationError({'format': ['Поддерживаются только csv, json и xlsx.']})


def export_properties(queryset, fmt: str, *, title: str | None = None) -> HttpResponse:
    rows = _property_export_rows(queryset)
    return _export_tabular(PROPERTY_EXPORT_DEFINITION, rows, fmt, title=title)


def _request_export_rows(queryset) -> list[dict]:
    rows: list[dict] = []
    for request_obj in queryset.select_related(
        'client', 'agent', 'property', 'operation_type', 'status',
    ):
        rows.append({
            'id': request_obj.pk,
            'client_username': getattr(request_obj.client, 'username', ''),
            'client_email': getattr(request_obj.client, 'email', ''),
            'client_phone': getattr(request_obj.client, 'phone', ''),
            'agent_username': getattr(request_obj.agent, 'username', ''),
            'property_id': request_obj.property_id,
            'property_title': getattr(request_obj.property, 'title', ''),
            'operation_type_code': getattr(request_obj.operation_type, 'code', ''),
            'status_code': request_obj.status_code,
            'status_name': request_obj.status_display_name,
            'property_type': request_obj.property_type or '',
            'min_price': request_obj.min_price,
            'max_price': request_obj.max_price,
            'min_area': request_obj.min_area,
            'max_area': request_obj.max_area,
            'rooms_count': request_obj.rooms_count,
            'address_preferences': request_obj.address_preferences or '',
            'description': request_obj.description or '',
            'created_at': request_obj.created_at,
            'updated_at': request_obj.updated_at,
            'closed_at': request_obj.closed_at,
        })
    return rows


def export_requests(
    queryset,
    fmt: str,
    *,
    title: str | None = None,
) -> HttpResponse:
    return _export_tabular(
        REQUEST_EXPORT_DEFINITION,
        _request_export_rows(queryset),
        fmt,
        title=title,
    )


def _task_export_rows(queryset) -> list[dict]:
    rows: list[dict] = []
    for task_obj in queryset.select_related(
        'status', 'assignee', 'created_by', 'client', 'property',
        'request', 'deal',
    ):
        rows.append({
            'id': task_obj.pk,
            'title': task_obj.title,
            'task_type': task_obj.task_type,
            'task_type_display': task_obj.get_task_type_display(),
            'priority': task_obj.priority,
            'priority_display': task_obj.get_priority_display(),
            'status_code': getattr(task_obj.status, 'code', ''),
            'status_name': getattr(task_obj.status, 'name', ''),
            'assignee_username': getattr(task_obj.assignee, 'username', ''),
            'created_by_username': getattr(task_obj.created_by, 'username', ''),
            'client_username': getattr(task_obj.client, 'username', ''),
            'property_id': task_obj.property_id,
            'property_title': getattr(task_obj.property, 'title', ''),
            'request_id': task_obj.request_id,
            'deal_id': task_obj.deal_id,
            'due_date': task_obj.due_date,
            'completed_at': task_obj.completed_at,
            'is_auto_closed': task_obj.is_auto_closed,
            'result': task_obj.result,
            'created_at': task_obj.created_at,
            'updated_at': task_obj.updated_at,
        })
    return rows


def export_tasks(
    queryset,
    fmt: str,
    *,
    title: str | None = None,
) -> HttpResponse:
    return _export_tabular(
        TASK_EXPORT_DEFINITION,
        _task_export_rows(queryset),
        fmt,
        title=title,
    )


def _deal_export_rows(queryset) -> list[dict]:
    rows: list[dict] = []
    for deal in queryset.select_related(
        'property', 'agent', 'client', 'operation_type', 'status',
        'request',
    ):
        rows.append({
            'id': deal.pk,
            'deal_number': deal.deal_number,
            'request_id': deal.request_id,
            'property_id': deal.property_id,
            'property_title': getattr(deal.property, 'title', ''),
            'agent_username': getattr(deal.agent, 'username', ''),
            'client_username': getattr(deal.client, 'username', ''),
            'operation_type_code': getattr(deal.operation_type, 'code', ''),
            'operation_type_name': getattr(deal.operation_type, 'name', ''),
            'status_code': getattr(deal.status, 'code', ''),
            'status_name': getattr(deal.status, 'name', ''),
            'price_final': deal.price_final,
            'commission_percent': deal.commission_percent,
            'commission_amount': deal.commission_amount,
            'deal_date': deal.deal_date,
            'contract_status': deal.contract_status,
            'contract_status_display': deal.get_contract_status_display(),
            'contract_requested_at': deal.contract_requested_at,
            'contract_generated_at': deal.contract_generated_at,
            'notes': deal.notes or '',
        })
    return rows


def export_deals(
    queryset,
    fmt: str,
    *,
    title: str | None = None,
) -> HttpResponse:
    return _export_tabular(
        DEAL_EXPORT_DEFINITION,
        _deal_export_rows(queryset),
        fmt,
        title=title,
    )


def _user_export_rows(queryset) -> list[dict]:
    rows: list[dict] = []
    for user in queryset.select_related('role'):
        rows.append({
            'id': user.pk,
            'username': user.username,
            'email': user.email or '',
            'phone': user.phone or '',
            'user_type': user.user_type,
            'user_type_display': user.get_user_type_display(),
            'role_code': getattr(user.role, 'code', ''),
            'role_name': getattr(user.role, 'name', ''),
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'is_email_verified': user.is_email_verified,
            'is_phone_verified': user.is_phone_verified,
            'created_at': user.created_at,
        })
    return rows


def export_users(queryset, fmt: str) -> HttpResponse:
    return _export_tabular(USER_EXPORT_DEFINITION, _user_export_rows(queryset), fmt)


def _dictionary_payload() -> dict[str, list[dict]]:
    payload: dict[str, list[dict]] = {}
    for definition in DICTIONARY_DEFINITIONS:
        payload[definition.code] = [
            {
                key: getattr(item, key, '')
                for key, _ in definition.columns
            }
            for item in definition.queryset
        ]
    return payload


def export_dictionaries(fmt: str) -> HttpResponse:
    payload = _dictionary_payload()
    suffix = timezone.localdate().strftime('%Y%m%d')
    normalized = (fmt or '').strip().lower()
    if normalized == 'json':
        response = HttpResponse(
            content_type='application/json; charset=utf-8',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="dictionaries-{suffix}.json"'
        )
        response.write(json.dumps({
            'exported_at': timezone.now().isoformat(),
            'items': payload,
        }, ensure_ascii=False, indent=2))
        return response
    if normalized == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="dictionaries-{suffix}.csv"'
        )
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['dictionary', 'field', 'value_map'])
        for definition in DICTIONARY_DEFINITIONS:
            for item in payload[definition.code]:
                writer.writerow([
                    definition.code,
                    ','.join(key for key, _ in definition.columns),
                    json.dumps(item, ensure_ascii=False),
                ])
        return response
    if normalized == 'xlsx':
        sheets = [
            WorkbookSheet.from_rows(
                definition.title,
                [
                    [label for _, label in definition.columns],
                    *[
                        [item.get(key, '') for key, _ in definition.columns]
                        for item in payload[definition.code]
                    ],
                ],
            )
            for definition in DICTIONARY_DEFINITIONS
        ]
        return _xlsx_response(f'dictionaries-{suffix}.xlsx', sheets)
    raise ValidationError({'format': ['Поддерживаются только csv, json и xlsx.']})
