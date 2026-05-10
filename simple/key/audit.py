"""Сервис записи единого журнала действий."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import FieldDoesNotExist
from django.utils.text import capfirst

from . import models


ENTITY_TYPES = {
    models.Property: 'property',
    models.Request: 'request',
    models.Task: 'task',
    models.Deal: 'deal',
}


def _entity_type_for(entity) -> str:
    for model, entity_type in ENTITY_TYPES.items():
        if isinstance(entity, model):
            return entity_type
    raise ValueError(f'Unsupported audit entity: {type(entity)!r}')


def _serialize_audit_value(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_serialize_audit_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _serialize_audit_value(item)
            for key, item in value.items()
        }
    return str(value)


def snapshot_fields(entity, field_names: list[str] | tuple[str, ...]) -> dict:
    snapshot = {}
    for field_name in field_names:
        try:
            field = entity._meta.get_field(field_name)
        except FieldDoesNotExist:
            continue
        value = getattr(entity, field.name, None)
        if field.is_relation:
            serialized_value = (
                None if value is None else {
                    'id': value.pk,
                    'label': (
                        value.username
                        if isinstance(value, models.User)
                        else str(value)
                    ),
                }
            )
        else:
            serialized_value = _serialize_audit_value(value)
        snapshot[field_name] = {
            'label': capfirst(str(field.verbose_name)),
            'value': serialized_value,
        }
    return snapshot


def diff_field_snapshots(before: dict, after: dict) -> dict:
    diff = {}
    for field_name, after_payload in after.items():
        before_payload = before.get(field_name, {})
        old_value = before_payload.get('value')
        new_value = after_payload.get('value')
        if old_value == new_value:
            continue
        diff[field_name] = {
            'label': after_payload.get('label') or before_payload.get('label') or field_name,
            'old': old_value,
            'new': new_value,
        }
    return diff


def log_event(
    *,
    entity,
    action_code: str,
    action_label: str,
    actor=None,
    message: str = '',
    metadata: dict | None = None,
    property_obj: models.Property | None = None,
    request_obj: models.Request | None = None,
    task_obj: models.Task | None = None,
    deal_obj: models.Deal | None = None,
) -> models.AuditLog:
    entity_type = _entity_type_for(entity)
    property_obj = property_obj or (entity if isinstance(entity, models.Property) else None)
    request_obj = request_obj or (entity if isinstance(entity, models.Request) else None)
    task_obj = task_obj or (entity if isinstance(entity, models.Task) else None)
    deal_obj = deal_obj or (entity if isinstance(entity, models.Deal) else None)

    return models.AuditLog.objects.create(
        entity_type=entity_type,
        entity_id=entity.pk,
        action_code=action_code,
        action_label=action_label,
        message=message or '',
        metadata=metadata or {},
        actor=actor if getattr(actor, 'pk', None) else None,
        property=property_obj,
        request=request_obj,
        task=task_obj,
        deal=deal_obj,
    )
