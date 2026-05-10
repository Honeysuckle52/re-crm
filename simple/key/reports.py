"""Сервисный слой отчётов и экспортов."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from html import escape

from django.db.models import Count, QuerySet, Sum
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
        ('assignee_username', 'Исполнитель'),
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


def _summary_pairs(summary: dict) -> list[tuple[str, str]]:
    return [(label, str(value)) for label, value in summary.items()]


def _export_csv(definition: ReportDefinition, summary: dict, rows: list[dict]) -> HttpResponse:
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{_report_filename(definition, "csv")}"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow([definition.title])
    writer.writerow([])
    writer.writerow(['Показатель', 'Значение'])
    for label, value in _summary_pairs(summary):
        writer.writerow([label, value])
    writer.writerow([])
    writer.writerow([label for _, label in definition.columns])
    for row in rows:
        writer.writerow([row.get(key, '') for key, _ in definition.columns])
    return response


def _export_json(definition: ReportDefinition, summary: dict, rows: list[dict], ordering: str) -> HttpResponse:
    response = HttpResponse(content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{_report_filename(definition, "json")}"'
    response.write(json.dumps({
        'report_code': definition.code,
        'title': definition.title,
        'ordering': ordering,
        'summary': summary,
        'rows': rows,
        'exported_at': timezone.now().isoformat(),
    }, ensure_ascii=False, indent=2))
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


def _export_xlsx(definition: ReportDefinition, summary: dict, rows: list[dict], ordering: str) -> HttpResponse:
    workbook = build_xlsx_bytes([
        WorkbookSheet.from_rows(
            'Сводка',
            [
                ('Отчёт', definition.title),
                ('Сортировка', ordering),
                (),
                ('Показатель', 'Значение'),
                *tuple(_summary_pairs(summary)),
            ],
        ),
        WorkbookSheet.from_rows(
            'Данные',
            [
                [label for _, label in definition.columns],
                *[
                    [row.get(key, '') for key, _ in definition.columns]
                    for row in rows
                ],
            ],
        ),
    ])
    response = HttpResponse(
        workbook,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{_report_filename(definition, "xlsx")}"'
    return response


def _export_pdf(definition: ReportDefinition, summary: dict, rows: list[dict]) -> HttpResponse:
    _ensure_fonts_registered()
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

    story = [Paragraph(definition.title, title_style), Spacer(1, 3 * mm)]
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
) -> HttpResponse:
    normalized = (fmt or '').strip().lower()
    if normalized == 'csv':
        return _export_csv(definition, summary, rows)
    if normalized == 'json':
        return _export_json(definition, summary, rows, ordering or definition.default_ordering)
    if normalized == 'xlsx':
        return _export_xlsx(
            definition,
            summary,
            rows,
            ordering or definition.default_ordering,
        )
    if normalized == 'xls':
        return _export_xls(definition, summary, rows)
    if normalized == 'pdf':
        return _export_pdf(definition, summary, rows)
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
        'summary': summary,
        'rows': rows,
        'ordering': ordering,
    }
