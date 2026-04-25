"""
Генерация PDF-договоров по сделкам.

Используется движок ReportLab + шрифты DejaVu Sans (обычный и жирный)
из каталога ``key/fonts/`` — DejaVu поддерживает полный диапазон
кириллицы, поэтому в документе корректно отображаются ФИО клиента,
адрес дома и подписи сторон.

Точка входа — :func:`render_contract_pdf`: принимает объект сделки
и возвращает ``ContentFile`` с PDF, готовым к сохранению в
``Deal.contract_file``.
"""
from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


# --- шрифты ----------------------------------------------------------------

FONTS_DIR = Path(__file__).resolve().parent / 'fonts'
FONT_REGULAR_PATH = FONTS_DIR / 'DejaVuSans.ttf'
FONT_BOLD_PATH = FONTS_DIR / 'DejaVuSans-Bold.ttf'

FONT_REGULAR = 'DejaVuSans'
FONT_BOLD = 'DejaVuSans-Bold'

_FONTS_REGISTERED = False


def _ensure_fonts_registered() -> None:
    """Регистрирует шрифты DejaVu в ReportLab один раз на процесс."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    if not FONT_REGULAR_PATH.exists() or not FONT_BOLD_PATH.exists():
        raise FileNotFoundError(
            f'Не найдены шрифты DejaVu в {FONTS_DIR}. '
            f'Ожидаются файлы DejaVuSans.ttf и DejaVuSans-Bold.ttf.'
        )
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_REGULAR_PATH)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_BOLD_PATH)))
    _FONTS_REGISTERED = True


# --- форматирование --------------------------------------------------------

def _money(value) -> str:
    """Формат цены с разделителями тысяч: 12 345 678 ₽."""
    if value is None:
        return '—'
    try:
        num = Decimal(str(value))
    except Exception:
        return str(value)
    whole, _, frac = f'{num:.2f}'.partition('.')
    with_spaces = ' '.join(
        whole[max(i - 3, 0):i] for i in range(len(whole), 0, -3)
    )
    # restore order
    groups = []
    s = whole
    while len(s) > 3:
        groups.insert(0, s[-3:])
        s = s[:-3]
    if s:
        groups.insert(0, s)
    pretty = ' '.join(groups)
    return f'{pretty},{frac} ₽'


def _client_full_name(client) -> str:
    profile = getattr(client, 'client_profile', None)
    if profile:
        parts = [profile.last_name, profile.first_name]
        if profile.middle_name:
            parts.append(profile.middle_name)
        return ' '.join(p for p in parts if p).strip() or client.username
    return client.username


def _agent_full_name(agent) -> str:
    profile = getattr(agent, 'employee_profile', None)
    if profile:
        parts = [profile.last_name, profile.first_name]
        if profile.middle_name:
            parts.append(profile.middle_name)
        name = ' '.join(p for p in parts if p).strip()
        if profile.position:
            return f'{name} ({profile.position})' if name else profile.position
        return name or agent.username
    return agent.username


def _property_address(prop) -> str:
    """Человекочитаемая строка адреса объекта."""
    try:
        return str(prop.address)
    except Exception:
        return f'Объект №{prop.pk}'


def _passport_line(client) -> str:
    p = getattr(client, 'client_profile', None)
    if not p or not (p.passport_series or p.passport_number):
        return '—'
    pieces = []
    if p.passport_series and p.passport_number:
        pieces.append(f'серия {p.passport_series} № {p.passport_number}')
    if p.passport_issued_by:
        pieces.append(f'выдан: {p.passport_issued_by}')
    if p.passport_issued_date:
        pieces.append(f'дата выдачи: {p.passport_issued_date:%d.%m.%Y}')
    return ', '.join(pieces) or '—'


# --- сборка PDF ------------------------------------------------------------

def render_contract_pdf(deal) -> ContentFile:
    """
    Собирает PDF-договор по сделке ``deal`` и возвращает
    :class:`django.core.files.base.ContentFile`.

    Файл НЕ сохраняется в БД — это задача вызывающего кода
    (``deal.contract_file.save(...)``).
    """
    _ensure_fonts_registered()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f'Договор по сделке {deal.deal_number}',
        author='Агентство недвижимости',
    )

    base = getSampleStyleSheet()['BodyText']
    style_body = ParagraphStyle(
        'Body', parent=base, fontName=FONT_REGULAR,
        fontSize=10.5, leading=14, spaceAfter=6,
    )
    style_small = ParagraphStyle(
        'Small', parent=style_body, fontSize=9, leading=12,
        textColor=colors.HexColor('#555555'),
    )
    style_h1 = ParagraphStyle(
        'H1', parent=style_body, fontName=FONT_BOLD,
        fontSize=16, leading=20, alignment=1, spaceAfter=4,
    )
    style_h2 = ParagraphStyle(
        'H2', parent=style_body, fontName=FONT_BOLD,
        fontSize=12, leading=16, spaceBefore=10, spaceAfter=4,
    )
    style_center = ParagraphStyle(
        'Center', parent=style_body, alignment=1,
    )

    story = []

    # --- шапка ---
    story.append(Paragraph('ДОГОВОР', style_h1))
    story.append(Paragraph(
        f'№ {deal.deal_number} от {deal.deal_date:%d.%m.%Y}',
        style_center,
    ))
    op_name = deal.operation_type.name if deal.operation_type_id else '—'
    story.append(Paragraph(
        f'Предмет: {op_name.lower()} объекта недвижимости', style_center,
    ))
    story.append(Spacer(1, 8))

    # --- стороны ---
    story.append(Paragraph('1. Стороны договора', style_h2))
    parties = [
        ['Агентство (исполнитель):',
         Paragraph(_agent_full_name(deal.agent), style_body)],
        ['Клиент (заказчик):',
         Paragraph(_client_full_name(deal.client), style_body)],
        ['Паспортные данные клиента:',
         Paragraph(_passport_line(deal.client), style_body)],
        ['Контакт клиента:',
         Paragraph(
             f'{deal.client.email or "—"} / {deal.client.phone or "—"}',
             style_body,
         )],
    ]
    table_parties = Table(parties, colWidths=[55 * mm, 110 * mm])
    table_parties.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), FONT_BOLD),
        ('FONTNAME', (1, 0), (1, -1), FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(table_parties)

    # --- объект ---
    story.append(Paragraph('2. Объект недвижимости', style_h2))
    prop = deal.property
    rows_prop = [
        ['Наименование:', prop.title or f'Объект №{prop.pk}'],
        ['Адрес:', _property_address(prop)],
        ['Тип операции:', op_name],
    ]
    if prop.area_total:
        rows_prop.append(['Общая площадь:', f'{prop.area_total} м²'])
    if prop.rooms_count:
        rows_prop.append(['Комнат:', str(prop.rooms_count)])
    if prop.floor_number and prop.total_floors:
        rows_prop.append(
            ['Этаж:', f'{prop.floor_number} из {prop.total_floors}']
        )
    rows_prop = [
        [k, Paragraph(str(v), style_body)] for k, v in rows_prop
    ]
    table_prop = Table(rows_prop, colWidths=[55 * mm, 110 * mm])
    table_prop.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), FONT_BOLD),
        ('FONTNAME', (1, 0), (1, -1), FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(table_prop)

    # --- финансы ---
    story.append(Paragraph('3. Финансовые условия', style_h2))
    rows_money = [
        ['Стоимость объекта:', _money(deal.price_final)],
        ['Комиссия агентства:',
         f'{deal.commission_percent or "—"}% '
         f'({_money(deal.commission_amount)})'],
    ]
    rows_money = [
        [k, Paragraph(str(v), style_body)] for k, v in rows_money
    ]
    table_money = Table(rows_money, colWidths=[55 * mm, 110 * mm])
    table_money.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), FONT_BOLD),
        ('FONTNAME', (1, 0), (1, -1), FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(table_money)

    # --- условия ---
    story.append(Paragraph('4. Предмет и условия', style_h2))
    story.append(Paragraph(
        'Исполнитель (агентство) обязуется оказать Заказчику (клиенту) '
        'услуги по сопровождению сделки с вышеуказанным объектом '
        'недвижимости. Заказчик обязуется принять и оплатить услуги '
        'в размере, определённом разделом 3 настоящего договора.',
        style_body,
    ))
    story.append(Paragraph(
        'Настоящий договор вступает в силу с момента подписания '
        'сторонами и действует до полного исполнения обязательств.',
        style_body,
    ))
    if deal.notes:
        story.append(Paragraph('Дополнительные условия:', style_h2))
        story.append(Paragraph(deal.notes, style_body))

    # --- подписи ---
    story.append(Spacer(1, 18))
    signatures = [
        [
            Paragraph('<b>Агентство:</b><br/>'
                      f'{_agent_full_name(deal.agent)}<br/><br/>'
                      '_______________ / подпись /', style_body),
            Paragraph('<b>Клиент:</b><br/>'
                      f'{_client_full_name(deal.client)}<br/><br/>'
                      '_______________ / подпись /', style_body),
        ]
    ]
    table_sig = Table(signatures, colWidths=[82 * mm, 82 * mm])
    table_sig.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(table_sig)

    # --- футер ---
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        f'Документ сформирован автоматически CRM агентства '
        f'{timezone.now():%d.%m.%Y %H:%M}.',
        style_small,
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return ContentFile(pdf_bytes, name=f'contract-{deal.deal_number}.pdf')
