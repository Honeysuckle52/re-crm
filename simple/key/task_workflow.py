"""Серверное описание и валидация workflow задач."""
from __future__ import annotations

from dataclasses import dataclass

from rest_framework.exceptions import ValidationError

from . import models

MATCH_TASK_TYPES = {'property_search', 'showing'}

CONTACT_STEP = 'contact'
REQUEST_STEP = 'request'
MATCH_STEP = 'match'
COMPLETE_STEP = 'complete'
COMPLETED_LOG_STEP = 'completed'

STEP_LABELS = {
    CONTACT_STEP: 'Контакт с клиентом',
    REQUEST_STEP: 'Заявка',
    MATCH_STEP: 'Подбор/выполнение',
    COMPLETE_STEP: 'Завершение',
}

STEP_OUTCOMES = {
    CONTACT_STEP: {
        'called': 'позвонил',
        'messaged': 'написал',
        'missed': 'не дозвонился',
    },
    REQUEST_STEP: {
        'created': 'создана новая заявка',
        'linked': 'связана с существующей заявкой',
        'exists': 'использована активная заявка клиента',
    },
    MATCH_STEP: {
        'proposed': 'предложил варианты',
        'showing_scheduled': 'назначил показ',
        'confirmed': 'клиент подтвердил вариант',
    },
}


@dataclass(frozen=True)
class WorkflowStepSpec:
    id: str
    label: str
    outcome_labels: dict[str, str]


CONTACT_SPEC = WorkflowStepSpec(
    id=CONTACT_STEP,
    label=STEP_LABELS[CONTACT_STEP],
    outcome_labels=STEP_OUTCOMES[CONTACT_STEP],
)
REQUEST_SPEC = WorkflowStepSpec(
    id=REQUEST_STEP,
    label=STEP_LABELS[REQUEST_STEP],
    outcome_labels=STEP_OUTCOMES[REQUEST_STEP],
)
MATCH_SPEC = WorkflowStepSpec(
    id=MATCH_STEP,
    label=STEP_LABELS[MATCH_STEP],
    outcome_labels=STEP_OUTCOMES[MATCH_STEP],
)
COMPLETE_SPEC = WorkflowStepSpec(
    id=COMPLETE_STEP,
    label=STEP_LABELS[COMPLETE_STEP],
    outcome_labels={},
)


def _normalize_step_id(step: str | None) -> str:
    if step == COMPLETED_LOG_STEP:
        return COMPLETE_STEP
    return (step or '').strip()


def _step_specs_for_task(task: models.Task) -> tuple[WorkflowStepSpec, ...]:
    specs = [CONTACT_SPEC, REQUEST_SPEC]
    if task.task_type in MATCH_TASK_TYPES:
        specs.append(MATCH_SPEC)
    specs.append(COMPLETE_SPEC)
    return tuple(specs)


def _recordable_step_specs(task: models.Task) -> tuple[WorkflowStepSpec, ...]:
    return tuple(
        spec for spec in _step_specs_for_task(task)
        if spec.id != COMPLETE_STEP
    )


def recorded_step_ids(task: models.Task) -> set[str]:
    step_ids: set[str] = set()
    for entry in task.steps_log or []:
        normalized = _normalize_step_id(entry.get('step'))
        if normalized in STEP_LABELS:
            step_ids.add(normalized)
    if task.is_terminal:
        step_ids.add(COMPLETE_STEP)
    return step_ids


def current_step_id(task: models.Task) -> str:
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

    if step_id != MATCH_STEP:
        return

    if not task.request_id:
        raise ValidationError(
            {'detail': 'Для этапа подбора задача должна быть связана с заявкой.'}
        )

    if outcome == 'confirmed':
        has_confirmed_match = task.request.matches.filter(
            is_confirmed=True,
            is_rejected=False,
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
