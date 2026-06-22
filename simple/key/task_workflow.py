# -*- coding: utf-8 -*-
"""Серверное описание и валидация workflow задач."""
from __future__ import annotations

from dataclasses import dataclass

from rest_framework.exceptions import ValidationError

from . import models

MATCH_TASK_TYPES = {'property_search', 'showing'}
SHOWING_TASK_TYPES = {'showing'}

CONTACT_STEP = 'contact'
REQUEST_STEP = 'request'
MATCH_STEP = 'match'
PAYMENT_STEP = 'payment'
COMPLETE_STEP = 'complete'
COMPLETED_LOG_STEP = 'completed'


@dataclass(frozen=True)
class WorkflowStepSpec:
    id: str
    label: str
    outcome_labels: dict[str, str]


def _normalize_step_id(step: str | None) -> str:
    if step == COMPLETED_LOG_STEP:
        return COMPLETE_STEP
    return (step or '').strip()


def _schema_step_to_spec(step: dict) -> WorkflowStepSpec:
    outcomes = {}
    for outcome in step.get('outcomes') or []:
        code = (outcome.get('code') or '').strip()
        if not code:
            continue
        outcomes[code] = outcome.get('label') or code
    return WorkflowStepSpec(
        id=step.get('id') or '',
        label=step.get('label') or step.get('id') or 'Шаг',
        outcome_labels=outcomes,
    )


TASK_DEFAULT_SCHEMA = [
    {
        'id': CONTACT_STEP,
        'label': 'Контакт с клиентом',
        'outcomes': [
            {'code': 'called', 'label': 'позвонил'},
            {'code': 'messaged', 'label': 'написал'},
            {'code': 'in_person', 'label': 'клиент присутствует лично'},
            {'code': 'missed', 'label': 'не дозвонился'},
        ],
    },
    {
        'id': REQUEST_STEP,
        'label': 'Заявка',
        'outcomes': [
            {'code': 'created', 'label': 'создана новая заявка'},
            {'code': 'linked', 'label': 'связана с существующей заявкой'},
            {'code': 'exists', 'label': 'использована активная заявка клиента'},
        ],
    },
    {
        'id': COMPLETE_STEP,
        'label': 'Завершение',
        'outcomes': [],
    },
]

TASK_MATCH_SCHEMA = [
    TASK_DEFAULT_SCHEMA[0],
    TASK_DEFAULT_SCHEMA[1],
    {
        'id': MATCH_STEP,
        'label': 'Подбор/выполнение',
        'outcomes': [
            {'code': 'proposed', 'label': 'предложил варианты'},
            {'code': 'showing_scheduled', 'label': 'назначил показ'},
            {'code': 'confirmed', 'label': 'клиент подтвердил вариант'},
        ],
    },
    TASK_DEFAULT_SCHEMA[2],
]

TASK_SHOWING_SCHEMA = [
    TASK_DEFAULT_SCHEMA[0],
    TASK_DEFAULT_SCHEMA[1],
    {
        'id': MATCH_STEP,
        'label': 'Предпросмотр объекта',
        'outcomes': [
            {'code': 'showing_scheduled', 'label': 'назначил реальный просмотр'},
            {'code': 'confirmed', 'label': 'клиент подтвердил просмотр'},
        ],
    },
    {
        'id': PAYMENT_STEP,
        'label': 'Оплата просмотра',
        'outcomes': [
            {'code': 'link_sent', 'label': 'отправил ссылку на оплату'},
        ],
    },
    TASK_DEFAULT_SCHEMA[2],
]


def _schema_for_task(task: models.Task) -> list[dict]:
    if task.task_type in SHOWING_TASK_TYPES:
        return TASK_SHOWING_SCHEMA
    if task.task_type in MATCH_TASK_TYPES:
        return TASK_MATCH_SCHEMA
    return TASK_DEFAULT_SCHEMA


def _step_specs_for_task(task: models.Task) -> tuple[WorkflowStepSpec, ...]:
    return tuple(
        _schema_step_to_spec(step)
        for step in _schema_for_task(task)
        if step.get('id')
    )


def _recordable_step_specs(task: models.Task) -> tuple[WorkflowStepSpec, ...]:
    return tuple(
        spec for spec in _step_specs_for_task(task)
        if spec.id != COMPLETE_STEP
    )


def recorded_step_ids(task: models.Task) -> set[str]:
    step_ids: set[str] = set()
    for entry in task.steps_log or []:
        normalized = _normalize_step_id(entry.get('step'))
        if any(spec.id == normalized for spec in _step_specs_for_task(task)):
            step_ids.add(normalized)
    if task.is_terminal:
        step_ids.add(COMPLETE_STEP)
    return step_ids


def current_step_id(task: models.Task) -> str:
    if task.is_terminal:
        return COMPLETE_STEP
    done_ids = recorded_step_ids(task)
    for spec in _step_specs_for_task(task):
        if spec.id not in done_ids:
            return spec.id
    return COMPLETE_STEP


def workflow_payload(task: models.Task) -> list[dict]:
    done_ids = recorded_step_ids(task)
    current_id = current_step_id(task)
    payload = []
    for spec in _step_specs_for_task(task):
        payload.append({
            'id': spec.id,
            'label': spec.label,
            'done': spec.id in done_ids,
            'current': spec.id == current_id,
            'outcomes': [
                {'code': code, 'label': label}
                for code, label in spec.outcome_labels.items()
            ],
        })
    return payload


def _expected_step(task: models.Task) -> WorkflowStepSpec | None:
    done_ids = recorded_step_ids(task)
    for spec in _recordable_step_specs(task):
        if spec.id not in done_ids:
            return spec
    return None


def _validate_step_preconditions(
    task: models.Task,
    *,
    step_id: str,
    outcome: str,
) -> None:
    if step_id == REQUEST_STEP and outcome in {'created', 'linked', 'exists'}:
        if not task.request_id:
            raise ValidationError(
                {'detail': 'Сначала привяжите или создайте заявку для задачи.'}
            )

    if step_id == PAYMENT_STEP:
        if task.task_type not in SHOWING_TASK_TYPES:
            raise ValidationError(
                {'detail': 'Этап оплаты доступен только для задач показа.'}
            )
        if not task.property_id or not task.client_id:
            raise ValidationError(
                {'detail': 'Для оплаты просмотра у задачи должны быть указаны клиент и объект.'}
            )
        viewing = models.PropertyViewing.objects.filter(
            property_id=task.property_id,
            client_profile__user_id=task.client_id,
        ).order_by('-viewing_date', '-id').first()
        payment = getattr(viewing, 'payment', None) if viewing else None
        if viewing is None:
            raise ValidationError(
                {'detail': 'Сначала назначьте реальный просмотр объекта.'}
            )
        if payment is None or not payment.payment_url:
            raise ValidationError(
                {'detail': 'Сначала сформируйте ссылку на оплату просмотра.'}
            )
        return

    if step_id != MATCH_STEP:
        return

    if not task.request_id:
        raise ValidationError(
            {'detail': 'Для этапа подбора задача должна быть связана с заявкой.'}
        )

    if task.task_type in SHOWING_TASK_TYPES and outcome == 'showing_scheduled':
        if not task.property_id or not task.client_id:
            raise ValidationError(
                {'detail': 'Для назначения просмотра укажите в задаче клиента и объект.'}
            )
        return

    if outcome == 'confirmed':
        has_confirmed_match = task.request.matches.filter(
            confirmed_at__isnull=False,
        ).exists()
        if not has_confirmed_match:
            raise ValidationError({
                'detail': (
                    'Нельзя отметить подтверждение: по заявке нет '
                    'подтверждённого варианта.'
                )
            })


def validate_record_step(
    task: models.Task,
    *,
    step: str,
    outcome: str | None = None,
) -> WorkflowStepSpec:
    if task.is_terminal:
        raise ValidationError(
            {'detail': 'Нельзя фиксировать этапы у завершённой задачи.'}
        )

    normalized_step = _normalize_step_id(step)
    spec_map = {spec.id: spec for spec in _recordable_step_specs(task)}
    spec = spec_map.get(normalized_step)
    if spec is None:
        raise ValidationError(
            {'detail': f'Этап «{step or "—"}» недоступен для этой задачи.'}
        )

    normalized_outcome = (outcome or '').strip()
    if not normalized_outcome:
        raise ValidationError(
            {'detail': f'Для этапа «{spec.label}» нужно указать outcome.'}
        )
    if normalized_outcome not in spec.outcome_labels:
        allowed = ', '.join(spec.outcome_labels.keys())
        raise ValidationError({
            'detail': (
                f'Для этапа «{spec.label}» допустимы только outcome: {allowed}.'
            )
        })

    expected = _expected_step(task)
    if expected is None:
        raise ValidationError(
            {'detail': 'Все этапы workflow уже зафиксированы.'}
        )
    if spec.id != expected.id:
        if spec.id in recorded_step_ids(task):
            raise ValidationError(
                {'detail': f'Этап «{spec.label}» уже зафиксирован.'}
            )
        raise ValidationError(
            {'detail': f'Сначала зафиксируйте этап «{expected.label}».'}
        )

    _validate_step_preconditions(
        task,
        step_id=spec.id,
        outcome=normalized_outcome,
    )
    return spec


__all__ = [
    'COMPLETED_LOG_STEP',
    'COMPLETE_STEP',
    'MATCH_TASK_TYPES',
    'current_step_id',
    'recorded_step_ids',
    'validate_record_step',
    'workflow_payload',
]
