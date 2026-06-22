# -*- coding: utf-8 -*-
"""Сервисный слой отчётов и экспортов."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from html import escape

from django.db.models import Count, Q, QuerySet, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import models
from .documents import FONT_BOLD, FONT_REGULAR, _ensure_fonts_registered
from .export_formatting import build_export_filename, format_export_data
from .xlsx_utils import WorkbookSheet, build_xlsx_bytes


@dataclass(frozen=True)
class ReportDefinition:
    code: str
    title: str
    filename_prefix: str
    columns: tuple[tuple[str, str], ...]
    default_ordering: str
    ordering_options: tuple[tuple[str, str], ...]


DEALS_REPORT = ReportDefinition(
    code='deals',
    title='Отчёт по сделкам',
    filename_prefix='deals-report',
    columns=(
        ('deal_number', 'Сделка'),
        ('deal_date', 'Дата'),
        ('status_name', 'Статус'),
        ('agent_username', 'Агент'),
        ('client_username', 'Клиент'),
        ('property_title', 'Объект'),
        ('price_final', 'Сумма'),
        ('commission_amount', 'Комиссия'),
        ('contract_status', 'Договор'),
    ),
    default_ordering='-deal_date',
    ordering_options=(
        ('-deal_date', 'Дата: сначала новые'),
        ('deal_date', 'Дата: сначала старые'),
        ('-price_final', 'Сумма: по убыванию'),
        ('price_final', 'Сумма: по возрастанию'),
        ('-commission_amount', 'Комиссия: по убыванию'),
        ('commission_amount', 'Комиссия: по возрастанию'),
        ('deal_number', 'Номер: А-Я'),
        ('-deal_number', 'Номер: Я-А'),
    ),
)

TASKS_REPORT = ReportDefinition(
    code='tasks',
    title='Отчёт по задачам сотрудников',
    filename_prefix='tasks-report',
    columns=(
        ('id', 'ID'),
        ('title', 'Задача'),
        ('task_type_display', 'Тип'),
        ('status_name', 'Статус'),
        ('assignee_username', 'Агент'),
        ('client_username', 'Клиент'),
        ('request_label', 'Заявка'),
        ('due_date', 'Срок'),
        ('completed_at', 'Завершена'),
        ('result_summary', 'Результат'),
    ),
    default_ordering='-created_at',
    ordering_options=(
        ('-created_at', 'Создание: сначала новые'),
        ('created_at', 'Создание: сначала старые'),
        ('due_date', 'Срок: сначала ранние'),
        ('-due_date', 'Срок: сначала поздние'),
        ('title', 'Название: А-Я'),
        ('-title', 'Название: Я-А'),
        ('priority', 'Приоритет: по возрастанию'),
        ('-priority', 'Приоритет: по убыванию'),
    ),
)

PROPERTIES_REPORT = ReportDefinition(
    code='properties',
    title='Отчёт по объектам недвижимости',
    filename_prefix='properties-report',
    columns=(
        ('id', 'ID'),
        ('title', 'Название'),
        ('property_type', 'Тип объекта'),
        ('operation_type', 'Операция'),
        ('status_name', 'Статус'),
        ('address', 'Адрес'),
        ('price', 'Цена'),
        ('area_total', 'Площадь (м²)'),
        ('rooms_count', 'Комнат'),
        ('floor_number', 'Этаж'),
        ('is_published', 'Опубликован'),
        ('created_at', 'Дата добавления'),
    ),
    default_ordering='-created_at',
    ordering_options=(
        ('-created_at', 'Дата: сначала новые'),
        ('created_at', 'Дата: сначала старые'),
        ('-price', 'Цена: по убыванию'),
        ('price', 'Цена: по возрастанию'),
        ('-area_total', 'Площадь: по убыванию'),
        ('area_total', 'Площадь: по возрастанию'),
        ('title', 'Название: А-Я'),
        ('-title', 'Название: Я-А'),
    ),
)

REQUESTS_REPORT = ReportDefinition(
    code='requests',
    title='Отчёт по заявкам клиентов',
    filename_prefix='requests-report',
    columns=(
        ('id', 'ID'),
        ('client_username', 'Клиент'),
        ('employee_username', 'Сотрудник'),
        ('operation_type', 'Операция'),
        ('property_type', 'Тип объекта'),
        ('status_name', 'Статус'),
        ('price_range', 'Бюджет'),
        ('area_range', 'Площадь'),
        ('rooms_count', 'Комнат'),
        ('preferred_city', 'Город'),
        ('created_at', 'Дата создания'),
        ('closed_at', 'Дата закрытия'),
    ),
    default_ordering='-created_at',
    ordering_options=(
        ('-created_at', 'Дата: сначала новые'),
        ('created_at', 'Дата: сначала старые'),
        ('status__code', 'Статус: А-Я'),
        ('-status__code', 'Статус: Я-А'),
    ),
)

VIEWING_PAYMENTS_REPORT = ReportDefinition(
    code='viewing-payments',
    title='Отчёт по оплатам просмотров',
    filename_prefix='viewing-payments-report',
    columns=(
        ('created_at', 'Создан'),
        ('client_username', 'Клиент'),
        ('agent_username', 'Агент'),
        ('property_title', 'Объект'),
        ('amount', 'Сумма'),
        ('status', 'Статус'),
        ('paid_at', 'Оплачен'),
    ),
    default_ordering='-created_at',
    ordering_options=(
        ('-created_at', 'Создание: сначала новые'),
        ('created_at', 'Создание: сначала старые'),
        ('-amount', 'Сумма: по убыванию'),
        ('amount', 'Сумма: по возрастанию'),
    ),
)


def _parse_date_param(params, key: str) -> date | None:
    raw = (params.get(key) or '').strip()
    if not raw:
        return None
    parsed = parse_date(raw)
    if parsed is None:
        raise ValidationError({key: [f'Неверный формат даты для параметра "{key}".']})
    return parsed


def _format_date(value) -> str:
    if not value:
        return '—'
    if hasattr(value, 'astimezone'):
        value = timezone.localtime(value)
    return value.strftime('%d.%m.%Y')


def _format_money(value) -> str:
    if value in (None, ''):
        return '0 ₽'
    amount = Decimal(str(value))
    text = f'{amount:,.2f}'.replace(',', ' ').replace('.00', '')
    return f'{text} ₽'


def _format_task_result(value) -> str:
    if not value:
        return '—'
    if isinstance(value, str):
        return value
    return value.get('summary') or '—'


def _resolve_ordering(params, definition: ReportDefinition) -> str:
    raw = (params.get('ordering') or '').strip()
    allowed = {code for code, _ in definition.ordering_options}
    if raw in allowed:
        return raw
    return definition.default_ordering


def _ordered_queryset(qs: QuerySet, ordering: str) -> QuerySet:
    if ordering.lstrip('-') == 'id':
        return qs.order_by(ordering)
    return qs.order_by(ordering, '-id')


def _report_filename(definition: ReportDefinition, fmt: str) -> str:
    suffix = timezone.localdate().strftime('%Y%m%d')
    return f'{definition.filename_prefix}-{suffix}.{fmt}'


def _report_user_label(user) -> str:
    parts = [
        getattr(user, 'last_name', ''),
        getattr(user, 'first_name', ''),
        getattr(user, 'middle_name', ''),
    ]
    full_name = ' '.join(part for part in parts if part).strip()
    if full_name:
        return full_name
    return getattr(user, 'username', None) or getattr(user, 'email', None) or 'Пользователь'


def _report_title(definition: ReportDefinition, user) -> str:
    stamp = timezone.localtime(timezone.now()).strftime('%d.%m.%Y %H:%M')
    return f'{definition.title} · {_report_user_label(user)} · {stamp}'


def _summary_pairs(summary: dict) -> list[tuple[str, str]]:
    return [(label, str(value)) for label, value in summary.items()]


def _export_csv(
    definition: ReportDefinition,
    summary: dict,
    rows: list[dict],
    *,
    title: str | None = None,
    user=None,
) -> HttpResponse:
    report_title = title or definition.title
    response = HttpResponse(
        format_export_data(
            rows,
            'csv',
            columns=definition.columns,
            title=report_title,
            metadata=summary,
        ),
        content_type='text/csv; charset=utf-8',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="{build_export_filename(definition.code, user, "csv")}"'
    )
    return response


def _export_json(
    definition: ReportDefinition,
    summary: dict,
    rows: list[dict],
    ordering: str,
    *,
    title: str | None = None,
    user=None,
) -> HttpResponse:
    report_title = title or definition.title
    metadata = {
        'report_code': definition.code,
        'ordering': ordering,
        **summary,
    }
    response = HttpResponse(
        format_export_data(
            rows,
            'json',
            columns=definition.columns,
            title=report_title,
            metadata=metadata,
        ),
        content_type='application/json; charset=utf-8',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="{build_export_filename(definition.code, user, "json")}"'
    )
    return response


def _export_xls(definition: ReportDefinition, summary: dict, rows: list[dict]) -> HttpResponse:
    response = HttpResponse(
        content_type='application/vnd.ms-excel; charset=utf-8',
    )
    response['Content-Disposition'] = f'attachment; filename="{_report_filename(definition, "xls")}"'
    response.write('\ufeff')
    parts = [
        '<html><head><meta charset="utf-8"></head><body>',
        f'<h2>{escape(definition.title)}</h2>',
        '<table border="1" cellspacing="0" cellpadding="4">',
        '<tr><th>Показатель</th><th>Значение</th></tr>',
    ]
    for label, value in _summary_pairs(summary):
        parts.append(
            f'<tr><td>{escape(label)}</td><td>{escape(str(value))}</td></tr>',
        )
    parts.extend([
        '</table>',
        '<br />',
        '<table border="1" cellspacing="0" cellpadding="4">',
        '<tr>',
    ])
    for _, label in definition.columns:
        parts.append(f'<th>{escape(label)}</th>')
    parts.append('</tr>')
    for row in rows:
        parts.append('<tr>')
        for key, _ in definition.columns:
            parts.append(f'<td>{escape(str(row.get(key, "")))}</td>')
        parts.append('</tr>')
    parts.append('</table></body></html>')
    response.write(''.join(parts))
    return response


def _export_xlsx(
    definition: ReportDefinition,
    summary: dict,
    rows: list[dict],
    ordering: str,
    *,
    title: str | None = None,
    user=None,
) -> HttpResponse:
    report_title = title or definition.title
    workbook = build_xlsx_bytes([
        WorkbookSheet.from_rows(
            'Данные',
            format_export_data(
                rows,
                'xlsx',
                columns=definition.columns,
                title=report_title,
                metadata={'ordering': ordering, **summary},
            ),
        ),
    ])
    response = HttpResponse(
        workbook,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="{build_export_filename(definition.code, user, "xlsx")}"'
    )
    return response


def _export_pdf(
    definition: ReportDefinition,
    summary: dict,
    rows: list[dict],
    *,
    title: str | None = None,
) -> HttpResponse:
    _ensure_fonts_registered()
    report_title = title or definition.title
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName=FONT_BOLD,
        fontSize=14,
        leading=18,
        alignment=TA_LEFT,
        spaceAfter=8,
    )
    text_style = ParagraphStyle(
        'ReportText',
        parent=styles['BodyText'],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
    )
    head_style = ParagraphStyle(
        'ReportHead',
        parent=text_style,
        fontName=FONT_BOLD,
    )

    story = [Paragraph(report_title, title_style), Spacer(1, 3 * mm)]
    summary_data = [[
        Paragraph('<b>Показатель</b>', head_style),
        Paragraph('<b>Значение</b>', head_style),
    ]]
    for label, value in _summary_pairs(summary):
        summary_data.append([
            Paragraph(escape(label), text_style),
            Paragraph(escape(str(value)), text_style),
        ])
    summary_table = Table(summary_data, colWidths=[60 * mm, 50 * mm], repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.extend([summary_table, Spacer(1, 5 * mm)])

    table_data = [[Paragraph(f'<b>{escape(label)}</b>', head_style) for _, label in definition.columns]]
    if rows:
        for row in rows:
            table_data.append([
                Paragraph(escape(str(row.get(key, ''))), text_style)
                for key, _ in definition.columns
            ])
    else:
        table_data.append([
            Paragraph('Нет данных по выбранным фильтрам.', text_style),
        ] + [''] * (len(definition.columns) - 1))

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{_report_filename(definition, "pdf")}"'
    response.write(pdf_bytes)
    return response


def export_report(
    definition: ReportDefinition,
    summary: dict,
    rows: list[dict],
    fmt: str,
    *,
    ordering: str | None = None,
    title: str | None = None,
    user=None,
) -> HttpResponse:
    normalized = (fmt or '').strip().lower()
    if normalized == 'csv':
        return _export_csv(definition, summary, rows, title=title, user=user)
    if normalized == 'json':
        return _export_json(
            definition,
            summary,
            rows,
            ordering or definition.default_ordering,
            title=title,
            user=user,
        )
    if normalized == 'xlsx':
        return _export_xlsx(
            definition,
            summary,
            rows,
            ordering or definition.default_ordering,
            title=title,
            user=user,
        )
    if normalized == 'xls':
        return _export_xls(definition, summary, rows)
    if normalized == 'pdf':
        return _export_pdf(definition, summary, rows, title=title)
    raise ValidationError({'export': ['Поддерживаются только csv, json, xlsx, xls и pdf.']})


def _filter_employee(
    qs: QuerySet,
    user,
    *,
    field_name: str,
    value: str | None = None,
) -> QuerySet:
    value = (value or '').strip()
    if user.is_employee and not user.is_admin_or_manager:
        return qs.filter(**{field_name: user})
    if not value:
        return qs
    if value == 'me' and user.is_employee:
        return qs.filter(**{field_name: user})
    return qs.filter(**{f'{field_name}_id': value})


def build_deals_report(params, *, user) -> dict:
    date_from = _parse_date_param(params, 'date_from')
    date_to = _parse_date_param(params, 'date_to')
    ordering = _resolve_ordering(params, DEALS_REPORT)

    qs = models.Deal.objects.select_related(
        'status', 'agent', 'client', 'property',
    )
    qs = _filter_employee(qs, user, field_name='agent', value=params.get('agent'))

    status_id = (params.get('status') or '').strip()
    status_code = (params.get('status_code') or '').strip()
    if status_id:
        qs = qs.filter(status_id=status_id)
    elif status_code:
        qs = qs.filter(status__code=status_code)
    if date_from:
        qs = qs.filter(deal_date__gte=date_from)
    if date_to:
        qs = qs.filter(deal_date__lte=date_to)

    qs = _ordered_queryset(qs, ordering)

    summary_raw = qs.aggregate(
        total_count=Count('id'),
        total_sum=Sum('price_final'),
        total_commission=Sum('commission_amount'),
    )
    summary = {
        'Всего сделок': summary_raw['total_count'] or 0,
        'Сумма сделок': _format_money(summary_raw['total_sum'] or 0),
        'Комиссия': _format_money(summary_raw['total_commission'] or 0),
    }

    rows = [{
        'deal_number': deal.deal_number,
        'deal_date': _format_date(deal.deal_date),
        'status_name': deal.status.name if deal.status_id else '—',
        'agent_username': deal.agent.username if deal.agent_id else '—',
        'client_username': deal.client.username if deal.client_id else '—',
        'property_title': deal.property.title if deal.property_id else '—',
        'price_final': _format_money(deal.price_final),
        'commission_amount': _format_money(deal.commission_amount),
        'contract_status': deal.get_contract_status_display(),
    } for deal in qs]

    return {
        'definition': DEALS_REPORT,
        'title': _report_title(DEALS_REPORT, user),
        'summary': summary,
        'rows': rows,
        'ordering': ordering,
    }


def build_tasks_report(params, *, user) -> dict:
    date_from = _parse_date_param(params, 'date_from')
    date_to = _parse_date_param(params, 'date_to')
    ordering = _resolve_ordering(params, TASKS_REPORT)

    qs = models.Task.objects.select_related(
        'status', 'assignee', 'client', 'request',
    )
    qs = _filter_employee(qs, user, field_name='assignee', value=params.get('assignee'))

    status_id = (params.get('status') or '').strip()
    status_code = (params.get('status_code') or '').strip()
    task_type = (params.get('task_type') or '').strip()
    if status_id:
        qs = qs.filter(status_id=status_id)
    elif status_code:
        qs = qs.filter(status__code=status_code)
    if task_type:
        qs = qs.filter(task_type=task_type)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = _ordered_queryset(qs, ordering)

    summary = {
        'Всего задач': qs.count(),
        'Завершено': qs.filter(status__code='done').count(),
        'Активных': qs.exclude(status__code__in=models.Task.TERMINAL_STATUS_CODES).count(),
        'Просрочено': qs.filter(
            due_date__lt=timezone.now(),
            completed_at__isnull=True,
        ).exclude(status__code__in=models.Task.TERMINAL_STATUS_CODES).count(),
    }

    rows = [{
        'id': task.id,
        'title': task.title,
        'task_type_display': task.task_type_display,
        'status_name': task.status.name if task.status_id else '—',
        'assignee_username': task.assignee.username if task.assignee_id else '—',
        'client_username': task.client.username if task.client_id else '—',
        'request_label': f'#{task.request_id}' if task.request_id else '—',
        'due_date': _format_date(task.due_date),
        'completed_at': _format_date(task.completed_at),
        'result_summary': _format_task_result(task.result),
    } for task in qs]

    return {
        'definition': TASKS_REPORT,
        'title': _report_title(TASKS_REPORT, user),
        'summary': summary,
        'rows': rows,
        'ordering': ordering,
    }


def build_viewing_payments_report(params, *, user) -> dict:
    date_from = _parse_date_param(params, 'date_from')
    date_to = _parse_date_param(params, 'date_to')
    ordering = _resolve_ordering(params, VIEWING_PAYMENTS_REPORT)

    qs = models.ViewingPayment.objects.select_related(
        'client',
        'property',
        'viewing__employee_profile__user',
    )
    status_value = (params.get('status') or '').strip()
    if status_value:
        qs = qs.filter(status=status_value)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = _ordered_queryset(qs, ordering)

    paid_qs = qs.filter(status=models.ViewingPayment.STATUS_PAID)
    paid_count = paid_qs.count()
    total_count = qs.count()
    paid_sum = paid_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    failed_count = qs.filter(status=models.ViewingPayment.STATUS_FAILED).count()
    average_amount = (paid_sum / paid_count).quantize(Decimal('0.01')) if paid_count else Decimal('0.00')
    conversion = f'{((paid_count / total_count) * 100):.1f}%' if total_count else '0.0%'

    summary = {
        'Сумма оплат': _format_money(paid_sum),
        'Успешных оплат': paid_count,
        'Неуспешных оплат': failed_count,
        'Средний чек': _format_money(average_amount),
        'Конверсия': conversion,
    }

    rows = [{
        'created_at': _format_date(payment.created_at),
        'client_username': payment.client.username if payment.client_id else '—',
        'agent_username': (
            payment.viewing.employee_profile.user.username
            if payment.viewing_id and payment.viewing.employee_profile_id
            else '—'
        ),
        'property_title': payment.property.title if payment.property_id else '—',
        'amount': _format_money(payment.amount),
        'status': payment.get_status_display(),
        'paid_at': _format_date(payment.paid_at),
    } for payment in qs]

    return {
        'definition': VIEWING_PAYMENTS_REPORT,
        'title': _report_title(VIEWING_PAYMENTS_REPORT, user),
        'summary': summary,
        'rows': rows,
        'ordering': ordering,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Отчёт по объектам недвижимости
# ─────────────────────────────────────────────────────────────────────────────

def build_properties_report(params, *, user) -> dict:
    date_from = _parse_date_param(params, 'date_from')
    date_to = _parse_date_param(params, 'date_to')
    ordering = _resolve_ordering(params, PROPERTIES_REPORT)

    qs = models.Property.objects.select_related(
        'status', 'property_type_ref', 'operation_type', 'house__street__city',
    )

    property_type = (params.get('property_type') or '').strip()
    status_id = (params.get('status') or '').strip()
    operation_type_id = (params.get('operation_type') or '').strip()
    is_published = (params.get('is_published') or '').strip()

    if property_type:
        qs = qs.filter(property_type_ref__code=property_type)
    if status_id:
        qs = qs.filter(status_id=status_id)
    if operation_type_id:
        qs = qs.filter(operation_type_id=operation_type_id)
    if is_published == '1':
        qs = qs.filter(is_published=True)
    elif is_published == '0':
        qs = qs.filter(is_published=False)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    # ordering по полям
    if ordering in ('-created_at', 'created_at', '-price', 'price', '-area_total', 'area_total', 'title', '-title'):
        qs = _ordered_queryset(qs, ordering)
    else:
        qs = qs.order_by('-created_at', '-id')

    summary_raw = qs.aggregate(
        total_count=Count('id'),
        total_price=Sum('price'),
    )
    published_count = qs.filter(is_published=True).count()
    unpublished_count = qs.filter(is_published=False).count()

    summary = {
        'Всего объектов': summary_raw['total_count'] or 0,
        'Опубликовано': published_count,
        'Не опубликовано': unpublished_count,
        'Общая стоимость': _format_money(summary_raw['total_price'] or 0),
    }

    rows = []
    for prop in qs:
        # Адрес: House.__str__ возвращает «Город, Улица, д. N» (House → Street → City)
        address = '—'
        if prop.house_id:
            try:
                address = str(prop.house) or '—'
            except Exception:
                address = '—'
        rows.append({
            'id': prop.id,
            'title': prop.title or '—',
            'property_type': prop.property_type_ref.name if prop.property_type_ref_id else '—',
            'operation_type': prop.operation_type.name if prop.operation_type_id else '—',
            'status_name': prop.status.name if prop.status_id else '—',
            'address': address,
            'price': _format_money(prop.price),
            'area_total': (
                f'{prop.area_total:.1f}' if prop.area_total is not None else '—'
            ),
            'rooms_count': str(prop.rooms_count) if prop.rooms_count is not None else '—',
            'floor_number': str(prop.floor_number) if prop.floor_number is not None else '—',
            'is_published': 'Да' if prop.is_published else 'Нет',
            'created_at': _format_date(prop.created_at),
        })

    return {
        'definition': PROPERTIES_REPORT,
        'title': _report_title(PROPERTIES_REPORT, user),
        'summary': summary,
        'rows': rows,
        'ordering': ordering,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Отчёт по заявкам клиентов
# ─────────────────────────────────────────────────────────────────────────────

def build_requests_report(params, *, user) -> dict:
    date_from = _parse_date_param(params, 'date_from')
    date_to = _parse_date_param(params, 'date_to')
    ordering_raw = (params.get('ordering') or '').strip()
    valid_orderings = {code for code, _ in REQUESTS_REPORT.ordering_options}
    ordering = ordering_raw if ordering_raw in valid_orderings else REQUESTS_REPORT.default_ordering

    qs = models.Request.objects.select_related(
        'client_profile__user',
        'employee_profile__user',
        'status',
        'operation_type',
        'property_type',
        'preferred_city',
    )

    # Если пользователь — сотрудник без прав менеджера, показываем только его заявки
    if user.is_employee and not user.is_admin_or_manager:
        qs = qs.filter(employee_profile__user=user)

    status_id = (params.get('status') or '').strip()
    property_type = (params.get('property_type') or '').strip()
    employee_id = (params.get('assignee') or '').strip()

    if status_id:
        qs = qs.filter(status_id=status_id)
    if property_type:
        qs = qs.filter(property_type__code=property_type)
    if employee_id:
        if employee_id == 'me':
            qs = qs.filter(employee_profile__user=user)
        else:
            qs = qs.filter(employee_profile__user_id=employee_id)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    qs = qs.order_by(ordering, '-id')

    total_count = qs.count()
    active_count = qs.filter(status__code__in=models.Request.ACTIVE_STATUS_CODES).count()
    completed_count = qs.filter(status__code__in=models.Request.SUCCESS_STATUS_CODES).count()
    cancelled_count = qs.filter(
        status__code__in=[c for c in models.Request.TERMINAL_STATUS_CODES
                          if c not in models.Request.SUCCESS_STATUS_CODES]
    ).count()

    summary = {
        'Всего заявок': total_count,
        'Активных': active_count,
        'Завершённых': completed_count,
        'Отменённых / отклонённых': cancelled_count,
    }

    rows = []
    for req in qs:
        client_name = '—'
        if req.client_profile_id and req.client_profile.user_id:
            u = req.client_profile.user
            name_parts = [u.last_name, u.first_name, getattr(u, 'middle_name', '')]
            full = ' '.join(p for p in name_parts if p).strip()
            client_name = full or u.username

        employee_name = '—'
        if req.employee_profile_id and req.employee_profile.user_id:
            u = req.employee_profile.user
            name_parts = [u.last_name, u.first_name, getattr(u, 'middle_name', '')]
            full = ' '.join(p for p in name_parts if p).strip()
            employee_name = full or u.username

        price_parts = []
        if req.min_price is not None:
            price_parts.append(f'от {_format_money(req.min_price)}')
        if req.max_price is not None:
            price_parts.append(f'до {_format_money(req.max_price)}')

        area_parts = []
        if req.min_area is not None:
            area_parts.append(f'от {req.min_area:.1f}')
        if req.max_area is not None:
            area_parts.append(f'до {req.max_area:.1f}')

        rows.append({
            'id': req.id,
            'client_username': client_name,
            'employee_username': employee_name,
            'operation_type': req.operation_type.name if req.operation_type_id else '—',
            'property_type': req.property_type.name if req.property_type_id else '—',
            'status_name': req.status.name if req.status_id else '—',
            'price_range': ' '.join(price_parts) if price_parts else '—',
            'area_range': ' '.join(area_parts) + ' м²' if area_parts else '—',
            'rooms_count': str(req.rooms_count) if req.rooms_count is not None else '—',
            'preferred_city': req.preferred_city.name if req.preferred_city_id else '—',
            'created_at': _format_date(req.created_at),
            'closed_at': _format_date(req.closed_at),
        })

    return {
        'definition': REQUESTS_REPORT,
        'title': _report_title(REQUESTS_REPORT, user),
        'summary': summary,
        'rows': rows,
        'ordering': ordering,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Топ-агентов: задачи и сделки
# ─────────────────────────────────────────────────────────────────────────────

def build_top_agents_tasks(params, *, limit: int = 5) -> list[dict]:
    """
    Возвращает список лучших сотрудников по выполненным задачам.
    Каждая запись: {rank, full_name, username, done_count, total_count, rate}.
    """
    date_from = _parse_date_param(params, 'date_from')
    date_to = _parse_date_param(params, 'date_to')

    qs = models.Task.objects.filter(assignee__isnull=False)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    agent_totals = (
        qs.values('assignee_id', 'assignee__username',
                  'assignee__first_name', 'assignee__last_name')
          .annotate(
              total_count=Count('id'),
              done_count=Count('id', filter=Q(status__code='done')),
          )
          .order_by('-done_count', '-total_count')
    )

    # Обрабатываем лимит (0 или None = все)
    if limit and limit > 0:
        agent_totals = agent_totals[:limit]

    # Подгружаем отчество отдельно (middle_name может быть @property или DB-полем)
    agent_ids = [row['assignee_id'] for row in agent_totals]
    middle_names: dict[int, str] = {}
    for u in models.User.objects.filter(pk__in=agent_ids).only('id', 'middle_name'):
        middle_names[u.pk] = getattr(u, 'middle_name', '') or ''

    result = []
    for rank, row in enumerate(agent_totals, start=1):
        total = row['total_count'] or 0
        done = row['done_count'] or 0
        rate = f'{(done / total * 100):.1f}%' if total else '0.0%'
        name_parts = [
            row.get('assignee__last_name') or '',
            row.get('assignee__first_name') or '',
            middle_names.get(row['assignee_id'], ''),
        ]
        full_name = ' '.join(p for p in name_parts if p).strip() or row['assignee__username']
        result.append({
            'rank': rank,
            'full_name': full_name,
            'username': row['assignee__username'],
            'done_count': done,
            'total_count': total,
            'rate': rate,
        })
    return result


def build_top_agents_deals(params, *, limit: int = 5) -> list[dict]:
    """
    Возвращает список лучших сотрудников по комиссии и количеству сделок.
    Каждая запись: {rank, full_name, username, deals_count, total_commission}.
    """
    date_from = _parse_date_param(params, 'date_from')
    date_to = _parse_date_param(params, 'date_to')

    qs = models.Deal.objects.filter(
        agent__isnull=False,
        status__code='completed',
    )
    if date_from:
        qs = qs.filter(deal_date__gte=date_from)
    if date_to:
        qs = qs.filter(deal_date__lte=date_to)

    agent_totals = (
        qs.values(
            'agent_id',
            'agent__username',
            'agent__first_name',
            'agent__last_name',
        )
          .annotate(
              deals_count=Count('id'),
              total_commission=Sum('commission_amount'),
          )
          .order_by('-total_commission', '-deals_count')
    )

    if limit and limit > 0:
        agent_totals = agent_totals[:limit]

    result = []
    for rank, row in enumerate(agent_totals, start=1):
        name_parts = [
            row.get('agent__last_name') or '',
            row.get('agent__first_name') or '',
        ]
        full_name = ' '.join(p for p in name_parts if p).strip() or row['agent__username']
        result.append({
            'rank': rank,
            'full_name': full_name,
            'username': row['agent__username'],
            'deals_count': row['deals_count'] or 0,
            'total_commission': _format_money(row['total_commission'] or 0),
        })
    return result
