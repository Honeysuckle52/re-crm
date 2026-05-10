"""Схемы и активные версии бизнес-процессов."""
from __future__ import annotations

from copy import deepcopy

from . import models

REQUEST_PROCESS_CODE = 'request'
TASK_PROCESS_CODE = 'task'
REQUEST_SCOPE_CODE = 'request'
DEFAULT_TASK_SCOPE_CODE = 'other'
MATCH_TASK_TYPES = {'property_search', 'showing'}


def _step(step_id: str, label: str, outcomes: dict[str, str] | None = None) -> dict:
    return {
        'id': step_id,
        'label': label,
        'outcomes': [
            {'code': code, 'label': outcome_label}
            for code, outcome_label in (outcomes or {}).items()
        ],
    }


REQUEST_SCHEMA = [
    {'id': 'open', 'label': 'Открыта', 'terminal': False},
    {'id': 'processing', 'label': 'В обработке', 'terminal': False},
    {'id': 'completed', 'label': 'Завершена', 'terminal': True},
    {'id': 'cancelled', 'label': 'Отменена', 'terminal': True},
    {'id': 'rejected', 'label': 'Отклонена', 'terminal': True},
    {'id': 'lost', 'label': 'Потеряна', 'terminal': True},
]

TASK_DEFAULT_SCHEMA = [
    _step(
        'contact',
        'Контакт с клиентом',
        {
            'called': 'позвонил',
            'messaged': 'написал',
            'missed': 'не дозвонился',
        },
    ),
    _step(
        'request',
        'Заявка',
        {
            'created': 'создана новая заявка',
            'linked': 'связана с существующей заявкой',
            'exists': 'использована активная заявка клиента',
        },
    ),
    _step('complete', 'Завершение'),
]

TASK_MATCH_SCHEMA = [
    TASK_DEFAULT_SCHEMA[0],
    TASK_DEFAULT_SCHEMA[1],
    _step(
        'match',
        'Подбор/выполнение',
        {
            'proposed': 'предложил варианты',
            'showing_scheduled': 'назначил показ',
            'confirmed': 'клиент подтвердил вариант',
        },
    ),
    _step('complete', 'Завершение'),
]


def normalize_task_scope(task_type: str | None) -> str:
    normalized = (task_type or '').strip()
    if not normalized:
        return DEFAULT_TASK_SCOPE_CODE
    return normalized


def default_request_schema() -> list[dict]:
    return deepcopy(REQUEST_SCHEMA)


def default_task_schema(task_type: str | None) -> list[dict]:
    scope = normalize_task_scope(task_type)
    if scope in MATCH_TASK_TYPES:
        return deepcopy(TASK_MATCH_SCHEMA)
    return deepcopy(TASK_DEFAULT_SCHEMA)


def _fallback_schema(process_code: str, scope_code: str) -> list[dict]:
    if process_code == REQUEST_PROCESS_CODE:
        return default_request_schema()
    return default_task_schema(scope_code)


def active_version(process_code: str, *, scope_code: str = '') -> models.ProcessVersion | None:
    queryset = models.ProcessVersion.objects.filter(
        process_code=process_code,
        scope_code=scope_code,
    )
    version = queryset.filter(is_active=True).order_by('-version', '-id').first()
    if version is not None:
        return version
    return queryset.order_by('-version', '-id').first()


def request_schema(request_obj: models.Request) -> list[dict]:
    version = getattr(request_obj, 'process_version', None)
    if version is not None and version.schema:
        return deepcopy(version.schema)
    active = active_version(REQUEST_PROCESS_CODE, scope_code=REQUEST_SCOPE_CODE)
    if active is not None and active.schema:
        return deepcopy(active.schema)
    return default_request_schema()


def task_schema(task: models.Task) -> list[dict]:
    version = getattr(task, 'process_version', None)
    if version is not None and version.schema:
        return deepcopy(version.schema)
    scope_code = normalize_task_scope(task.task_type)
    active = active_version(TASK_PROCESS_CODE, scope_code=scope_code)
    if active is not None and active.schema:
        return deepcopy(active.schema)
    return _fallback_schema(TASK_PROCESS_CODE, scope_code)


def request_process_label(request_obj: models.Request) -> str:
    version = getattr(request_obj, 'process_version', None)
    if version is None:
        return 'Текущая версия по умолчанию'
    return f'{version.name} · v{version.version}'


def task_process_label(task: models.Task) -> str:
    version = getattr(task, 'process_version', None)
    if version is None:
        return 'Текущая версия по умолчанию'
    return f'{version.name} · v{version.version}'


def assign_request_process_version(request_obj: models.Request, *, save: bool = True):
    if request_obj.process_version_id:
        return request_obj.process_version
    version = active_version(REQUEST_PROCESS_CODE, scope_code=REQUEST_SCOPE_CODE)
    if version is None:
        return None
    request_obj.process_version = version
    if save:
        request_obj.save(update_fields=['process_version'])
    return version


def assign_task_process_version(
    task: models.Task,
    *,
    save: bool = True,
    reassign_for_scope_change: bool = False,
):
    scope_code = normalize_task_scope(task.task_type)
    current = getattr(task, 'process_version', None)
    should_assign = current is None or (
        reassign_for_scope_change and current.scope_code != scope_code
    )
    if not should_assign:
        return current
    version = active_version(TASK_PROCESS_CODE, scope_code=scope_code)
    if version is None:
        return current
    task.process_version = version
    if save:
        task.save(update_fields=['process_version'])
    return version


def next_version_number(process_code: str, *, scope_code: str = '') -> int:
    latest = (
        models.ProcessVersion.objects
        .filter(process_code=process_code, scope_code=scope_code)
        .order_by('-version')
        .first()
    )
    return (latest.version if latest is not None else 0) + 1
