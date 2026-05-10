"""Оркестрация жизненного цикла заявки клиента."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import audit as audit_service
from . import business_rules, models
from . import process_versions
from .deals_service import create_deal_from_request
from .mailing import (
    enqueue_property_matched,
    enqueue_request_closed,
    enqueue_request_taken,
)
from .task_actions import complete_task

REQUEST_STATUS_DEFAULT_NAMES = {
    'open': 'Открыта',
    'processing': 'В обработке',
    'completed': 'Завершена',
    'cancelled': 'Отменена',
    'rejected': 'Отклонена',
    'lost': 'Потеряна',
}


@dataclass
class RequestAssignmentResult:
    request: models.Request
    contact_task: models.Task | None
    queued_email: models.OutgoingEmail | None
    assignment_changed: bool


@dataclass
class MatchConfirmationResult:
    request: models.Request
    match: models.RequestPropertyMatch
    queued_email: models.OutgoingEmail | None
    auto_closed_tasks: int
    already_confirmed: bool


@dataclass
class RequestCloseResult:
    request: models.Request
    deal: models.Deal | None
    queued_email: models.OutgoingEmail | None


def _get_or_create_request_status(code: str) -> models.RequestStatus:
    return models.RequestStatus.objects.get_or_create(
        code=code,
        defaults={'name': REQUEST_STATUS_DEFAULT_NAMES.get(code, code)},
    )[0]


def _task_status_by_code(code: str) -> models.TaskStatus | None:
    return models.TaskStatus.objects.filter(code=code).first()


def _request_with_related(pk: int) -> models.Request:
    return (
        models.Request.objects
        .select_for_update()
        .select_related('status', 'client', 'operation_type')
        .get(pk=pk)
    )


def _ensure_processing_status(request_obj: models.Request) -> bool:
    if request_obj.status_code != 'open':
        return False
    processing = models.RequestStatus.objects.filter(code='processing').first()
    if not processing or request_obj.status_id == processing.pk:
        return False
    request_obj.status = processing
    return True


def _contact_task_title(request_obj: models.Request) -> str:
    return f'Связаться с клиентом по заявке №{request_obj.pk}'


def _contact_task_description(request_obj: models.Request) -> str:
    client_name = getattr(request_obj.client, 'username', 'клиентом')
    property_title = (
        request_obj.property.title
        if request_obj.property_id and request_obj.property
        else None
    )
    description_lines = [
        f'Свяжитесь с клиентом {client_name} по заявке №{request_obj.pk}.',
    ]
    if property_title:
        description_lines.append(f'Интересует объект: {property_title}.')
    if request_obj.description:
        description_lines.append(
            f'Пожелания клиента: {request_obj.description}',
        )
    return '\n'.join(description_lines)


def _ensure_contact_task(
    request_obj: models.Request,
    *,
    agent: models.User,
) -> tuple[models.Task | None, bool]:
    existing = (
        request_obj.tasks
        .filter(task_type='contact_client', assignee=agent)
        .order_by('-created_at')
        .first()
    )
    if existing is not None:
        return existing, False

    status_new = _task_status_by_code('new')
    if status_new is None:
        raise ValidationError(
            {'detail': 'Справочник статусов задач не заполнен: отсутствует код "new".'}
        )

    task = models.Task.objects.create(
        title=_contact_task_title(request_obj),
        description=_contact_task_description(request_obj),
        priority='high',
        task_type='contact_client',
        status=status_new,
        assignee=agent,
        created_by=agent,
        client=request_obj.client,
        property=request_obj.property,
        request=request_obj,
        due_date=timezone.now() + timedelta(hours=24),
    )
    process_versions.assign_task_process_version(task)
    return task, True


@transaction.atomic
def sync_request_assignment(
    request_obj: models.Request,
    *,
    previous_agent_id: int | None,
    actor=None,
) -> RequestAssignmentResult:
    req = _request_with_related(request_obj.pk)
    if not req.agent_id:
        return RequestAssignmentResult(
            request=req,
            contact_task=None,
            queued_email=None,
            assignment_changed=False,
        )

    assignment_changed = previous_agent_id != req.agent_id
    update_fields: list[str] = []
    if _ensure_processing_status(req):
        update_fields.extend(['status', 'updated_at'])
    if update_fields:
        req.save(update_fields=update_fields)

    contact_task, task_created = _ensure_contact_task(req, agent=req.agent)
    queued_email = None
    if assignment_changed:
        queued_email = enqueue_request_taken(request=req, agent=req.agent)
        audit_service.log_event(
            entity=req,
            action_code='assigned',
            action_label='Назначение агента',
            actor=actor,
            message=(
                f'Заявка назначена сотруднику {req.agent.username}.'
            ),
            metadata={
                'agent_id': req.agent_id,
                'previous_agent_id': previous_agent_id,
                'status_code': req.status_code,
            },
            property_obj=req.property,
        )
    if task_created and contact_task is not None:
        audit_service.log_event(
            entity=contact_task,
            action_code='created',
            action_label='Создание задачи',
            actor=actor or req.agent,
            message=(
                f'Автоматически создана контактная задача по заявке №{req.pk}.'
            ),
            metadata={
                'task_type': contact_task.task_type,
                'request_id': req.pk,
                'auto_created': True,
                'process_version_id': contact_task.process_version_id,
            },
            property_obj=req.property,
            request_obj=req,
        )

    return RequestAssignmentResult(
        request=req,
        contact_task=contact_task,
        queued_email=queued_email,
        assignment_changed=assignment_changed,
    )


@transaction.atomic
def create_request_from_serializer(
    serializer,
    *,
    actor,
) -> models.Request:
    extra: dict[str, object] = {}
    if actor.is_authenticated and actor.is_client:
        extra['client'] = actor
        extra['agent'] = None
    elif not serializer.validated_data.get('client'):
        raise ValidationError({'client': 'Укажите клиента заявки.'})

    assigned_agent = serializer.validated_data.get('agent')
    request_status = serializer.validated_data.get('status')
    if assigned_agent and (request_status is None or request_status.code == 'open'):
        processing = models.RequestStatus.objects.filter(code='processing').first()
        if processing:
            extra['status'] = processing

    request_obj = serializer.save(**extra)
    process_versions.assign_request_process_version(request_obj)
    audit_service.log_event(
        entity=request_obj,
        action_code='created',
        action_label='Создание заявки',
        actor=actor,
        message='Заявка создана.',
        metadata={
            'client_id': request_obj.client_id,
            'agent_id': request_obj.agent_id,
            'status_code': request_obj.status_code,
            'process_version_id': request_obj.process_version_id,
        },
        property_obj=request_obj.property,
    )
    if request_obj.agent_id:
        request_obj = sync_request_assignment(
            request_obj,
            previous_agent_id=None,
            actor=actor,
        ).request
    return request_obj


@transaction.atomic
def take_request(
    request_obj: models.Request,
    *,
    actor,
) -> RequestAssignmentResult:
    req = _request_with_related(request_obj.pk)

    if req.is_terminal:
        raise ValidationError('Нельзя взять в работу уже закрытую заявку.')
    if req.agent_id and req.agent_id != actor.id:
        raise ValidationError('Заявка уже взята другим сотрудником.')

    if not actor.is_admin_or_manager:
        business_rules.assert_can_take_request(actor, exclude_pk=req.pk)

    previous_agent_id = req.agent_id
    update_fields: list[str] = []
    if req.agent_id != actor.id:
        req.agent = actor
        update_fields.append('agent')
    if _ensure_processing_status(req):
        update_fields.append('status')
    if update_fields:
        req.save(update_fields=list(dict.fromkeys(update_fields + ['updated_at'])))

    return sync_request_assignment(
        req,
        previous_agent_id=previous_agent_id,
        actor=actor,
    )


@transaction.atomic
def confirm_request_match(
    request_obj: models.Request,
    *,
    match_id: int,
    actor,
) -> MatchConfirmationResult:
    req = _request_with_related(request_obj.pk)
    match = (
        req.matches
        .select_for_update()
        .select_related('property', 'agent')
        .filter(pk=match_id)
        .first()
    )
    if match is None:
        raise ValidationError('Вариант не найден.')
    if req.is_terminal:
        raise ValidationError('Нельзя подтверждать вариант по закрытой заявке.')

    req.matches.exclude(pk=match.pk).filter(
        is_confirmed=True,
    ).update(
        is_confirmed=False,
        confirmed_at=None,
        confirmed_by=None,
    )

    already_confirmed = (
        match.is_confirmed
        and match.is_offered
        and not match.is_rejected
    )
    if already_confirmed:
        return MatchConfirmationResult(
            request=req,
            match=match,
            queued_email=None,
            auto_closed_tasks=0,
            already_confirmed=True,
        )

    match.is_offered = True
    match.is_rejected = False
    match.is_confirmed = True
    match.confirmed_at = timezone.now()
    match.confirmed_by = actor
    match.save(update_fields=[
        'is_offered', 'is_rejected', 'is_confirmed',
        'confirmed_at', 'confirmed_by',
    ])

    auto_closed_tasks = 0
    active_search_tasks = models.Task.objects.filter(
        request=req,
        task_type='property_search',
        status__code__in=business_rules.ACTIVE_TASK_STATUS_CODES,
        completed_at__isnull=True,
    )
    for task in active_search_tasks:
        _, changed = complete_task(
            task,
            actor=actor,
            auto_closed=True,
            reason=(
                'Автозакрыто: клиент подтвердил вариант '
                f'«{match.property.title or "Объект №" + str(match.property.pk)}» '
                f'по заявке №{req.pk}.'
            ),
        )
        if changed:
            auto_closed_tasks += 1

    queued_email = enqueue_property_matched(
        request=req,
        property_obj=match.property,
        agent=actor,
    )
    audit_service.log_event(
        entity=req,
        action_code='match_confirmed',
        action_label='Подтверждение варианта',
        actor=actor,
        message=(
            f'Подтверждён вариант объекта №{match.property_id} по заявке.'
        ),
        metadata={
            'match_id': match.pk,
            'property_id': match.property_id,
            'auto_closed_tasks': auto_closed_tasks,
        },
        property_obj=match.property,
    )
    return MatchConfirmationResult(
        request=req,
        match=match,
        queued_email=queued_email,
        auto_closed_tasks=auto_closed_tasks,
        already_confirmed=False,
    )


@transaction.atomic
def close_request(
    request_obj: models.Request,
    *,
    outcome: str,
    actor,
) -> RequestCloseResult:
    req = _request_with_related(request_obj.pk)
    if req.is_terminal:
        raise ValidationError('Заявка уже закрыта.')

    req.status = _get_or_create_request_status(outcome)
    req.closed_at = timezone.now()
    req.save(update_fields=['status', 'closed_at', 'updated_at'])

    deal = None
    if outcome in models.Request.SUCCESS_STATUS_CODES:
        deal = create_deal_from_request(req, actor=actor)

    queued_email = enqueue_request_closed(request=req, actor=actor, deal=deal)
    audit_service.log_event(
        entity=req,
        action_code='closed',
        action_label='Закрытие заявки',
        actor=actor,
        message=(
            'Заявка завершена.'
            if outcome == 'completed' else
            f'Заявка закрыта с исходом «{req.status.name}».'
        ),
        metadata={
            'outcome': outcome,
            'deal_id': deal.pk if deal else None,
        },
        property_obj=req.property,
        deal_obj=deal,
    )
    return RequestCloseResult(
        request=req,
        deal=deal,
        queued_email=queued_email,
    )


__all__ = [
    'MatchConfirmationResult',
    'RequestAssignmentResult',
    'RequestCloseResult',
    'close_request',
    'confirm_request_match',
    'create_request_from_serializer',
    'sync_request_assignment',
    'take_request',
]
