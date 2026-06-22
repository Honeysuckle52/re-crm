# -*- coding: utf-8 -*-
"""Сборка PDF-договоров."""
from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FONT_REGULAR = 'TimesNewRoman'
FONT_BOLD = 'TimesNewRoman-Bold'
FONT_ITALIC = 'TimesNewRoman-Italic'
FONT_BOLD_ITALIC = 'TimesNewRoman-BoldItalic'

FONTS_DIR = Path(__file__).resolve().parent / 'fonts'
FONT_FILES = {
    FONT_REGULAR: FONTS_DIR / 'times.ttf',
    FONT_BOLD: FONTS_DIR / 'timesbd.ttf',
    FONT_ITALIC: FONTS_DIR / 'timesi.ttf',
    FONT_BOLD_ITALIC: FONTS_DIR / 'timesbi.ttf',
}

PAGE_WIDTH, PAGE_HEIGHT = A4
PAGE_MARGIN_LEFT = 25 * mm
PAGE_MARGIN_RIGHT = 15 * mm
PAGE_MARGIN_TOP = 20 * mm
PAGE_MARGIN_BOTTOM = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT
LABEL_WIDTH = 48 * mm
VALUE_WIDTH = CONTENT_WIDTH - LABEL_WIDTH

COLOR_BORDER = colors.black
COLOR_MUTED = colors.black
COLOR_PANEL = colors.white
COLOR_PANEL_STRONG = colors.white
COLOR_TEXT = colors.black

_FONTS_REGISTERED = False

UNITS_MALE = (
    '',
    'один',
    'два',
    'три',
    'четыре',
    'пять',
    'шесть',
    'семь',
    'восемь',
    'девять',
)
UNITS_FEMALE = (
    '',
    'одна',
    'две',
    'три',
    'четыре',
    'пять',
    'шесть',
    'семь',
    'восемь',
    'девять',
)
TEENS = (
    'десять',
    'одиннадцать',
    'двенадцать',
    'тринадцать',
    'четырнадцать',
    'пятнадцать',
    'шестнадцать',
    'семнадцать',
    'восемнадцать',
    'девятнадцать',
)
TENS = (
    '',
    '',
    'двадцать',
    'тридцать',
    'сорок',
    'пятьдесят',
    'шестьдесят',
    'семьдесят',
    'восемьдесят',
    'девяносто',
)
HUNDREDS = (
    '',
    'сто',
    'двести',
    'триста',
    'четыреста',
    'пятьсот',
    'шестьсот',
    'семьсот',
    'восемьсот',
    'девятьсот',
)
ORDERS = (
    (False, ('', '', '')),
    (True, ('тысяча', 'тысячи', 'тысяч')),
    (False, ('миллион', 'миллиона', 'миллионов')),
    (False, ('миллиард', 'миллиарда', 'миллиардов')),
    (False, ('триллион', 'триллиона', 'триллионов')),
)


def _ensure_fonts_registered() -> None:
    """Регистрирует Times New Roman из локальной папки fonts."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    for font_name, font_path in FONT_FILES.items():
        if not font_path.exists():
            raise FileNotFoundError(f'Missing PDF font file: {font_path}')
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    pdfmetrics.registerFontFamily(
        FONT_REGULAR,
        normal=FONT_REGULAR,
        bold=FONT_BOLD,
        italic=FONT_ITALIC,
        boldItalic=FONT_BOLD_ITALIC,
    )
    _FONTS_REGISTERED = True


def _money(value) -> str:
    """Формат цены с разделителями тысяч: 12 345 678,90 ₽."""
    if value is None:
        return '—'
    try:
        num = Decimal(str(value))
    except Exception:
        return str(value)
    whole, _, frac = f'{num:.2f}'.partition('.')
    groups = []
    digits = whole
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    if digits:
        groups.insert(0, digits)
    return f'{" ".join(groups)},{frac} ₽'


def _plural(value: int, forms: tuple[str, str, str]) -> str:
    value = abs(int(value))
    if value % 100 in {11, 12, 13, 14}:
        return forms[2]
    remainder = value % 10
    if remainder == 1:
        return forms[0]
    if remainder in {2, 3, 4}:
        return forms[1]
    return forms[2]


def _triplet_to_words(value: int, *, female: bool = False) -> str:
    if value == 0:
        return ''

    words: list[str] = []
    hundreds = value // 100
    tens_units = value % 100
    tens = tens_units // 10
    units = tens_units % 10

    if hundreds:
        words.append(HUNDREDS[hundreds])

    if 10 <= tens_units <= 19:
        words.append(TEENS[tens_units - 10])
    else:
        if tens:
            words.append(TENS[tens])
        if units:
            words.append((UNITS_FEMALE if female else UNITS_MALE)[units])

    return ' '.join(filter(None, words))


def _number_to_words(value: int) -> str:
    if value == 0:
        return 'ноль'

    parts: list[str] = []
    order_index = 0
    remaining = value

    while remaining > 0:
        remaining, triplet = divmod(remaining, 1000)
        if not triplet:
            order_index += 1
            continue

        order_female, order_forms = ORDERS[order_index]
        triplet_words = _triplet_to_words(triplet, female=order_female)
        chunk = triplet_words
        if order_index > 0:
            chunk = f'{chunk} {_plural(triplet, order_forms)}'.strip()
        parts.insert(0, chunk)
        order_index += 1

    return ' '.join(filter(None, parts))


def _money_words(value) -> str:
    if value is None:
        return '—'
    amount = Decimal(str(value)).quantize(Decimal('0.01'))
    rubles = int(amount)
    kopeks = int((amount - rubles) * 100)
    rubles_words = _number_to_words(rubles)
    text = (
        f'{rubles_words} {_plural(rubles, ("рубль", "рубля", "рублей"))} '
        f'{kopeks:02d} {_plural(kopeks, ("копейка", "копейки", "копеек"))}'
    )
    return text[:1].upper() + text[1:]


def _format_decimal(value, suffix: str = '') -> str:
    if value in (None, ''):
        return '—'
    try:
        num = Decimal(str(value))
    except Exception:
        return f'{value}{suffix}'
    normalized = f'{num:.2f}'.rstrip('0').rstrip('.').replace('.', ',')
    return f'{normalized}{suffix}'


def _format_date(value) -> str:
    if not value:
        return '—'
    return value.strftime('%d.%m.%Y')


def _as_text(value, fallback: str = '—') -> str:
    if value in (None, ''):
        return fallback
    return str(value)


def _paragraph_text(value, fallback: str = '—') -> str:
    return escape(_as_text(value, fallback)).replace('\n', '<br/>')


def _setting(name: str, default: str = '') -> str:
    return _as_text(getattr(settings, name, default), default)


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
        name = ' '.join(p for p in parts if p).strip()
        if profile.position:
            return f'{name} ({profile.position})' if name else profile.position
        return name or agent.username
    return agent.username


def _agent_position(agent) -> str:
    profile = getattr(agent, 'employee_profile', None)
    if profile and profile.position:
        return profile.position
    return 'ответственный специалист'


def _property_address(prop) -> str:
    """Человекочитаемая строка адреса объекта."""
    try:
        return str(prop.address)
    except Exception:
        return f'Объект №{prop.pk}'


def _deal_city(deal) -> str:
    try:
        city = deal.property.address.house.street.city
    except Exception:
        return 'г. ________'
    region = f', {city.region}' if getattr(city, 'region', None) else ''
    return f'г. {city.name}{region}'


def _passport_line(client) -> str:
    profile = getattr(client, 'client_profile', None)
    details = getattr(profile, 'individual_details', None) if profile else None
    if not details or not (details.passport_series or details.passport_number):
        return '—'
    pieces = []
    if details.passport_series and details.passport_number:
        pieces.append(
            f'серия {details.passport_series} № {details.passport_number}',
        )
    if details.passport_issued_by:
        pieces.append(f'выдан: {details.passport_issued_by}')
    if details.passport_code:
        pieces.append(f'код подразделения: {details.passport_code}')
    if details.passport_issued_date:
        pieces.append(f'дата выдачи: {details.passport_issued_date:%d.%m.%Y}')
    return ', '.join(pieces) or '—'


def _company_requisites_line(client) -> str:
    profile = getattr(client, 'client_profile', None)
    details = getattr(profile, 'company_details', None) if profile else None
    if not details:
        return '—'
    pieces = []
    if details.company_name:
        pieces.append(f'наименование: {details.company_name}')
    if details.company_inn:
        pieces.append(f'ИНН: {details.company_inn}')
    if details.company_kpp:
        pieces.append(f'КПП: {details.company_kpp}')
    if details.company_ogrn:
        pieces.append(f'ОГРН: {details.company_ogrn}')
    if details.legal_address:
        pieces.append(f'юридический адрес: {details.legal_address}')
    return ', '.join(pieces) or '—'


def _client_requisites_label(client) -> str:
    profile = getattr(client, 'client_profile', None)
    if profile and profile.client_kind == profile.CLIENT_KIND_COMPANY:
        return 'Реквизиты юрлица'
    return 'Паспортные данные'


def _client_requisites_line(client) -> str:
    profile = getattr(client, 'client_profile', None)
    if profile and profile.client_kind == profile.CLIENT_KIND_COMPANY:
        return _company_requisites_line(client)
    return _passport_line(client)


def _client_address_line(client) -> str:
    return '\u2014'


def _client_contact_line(client, *, include_preferred_contact_method: bool = True) -> str:
    profile = getattr(client, 'client_profile', None)
    parts = [client.phone or '—', client.email or '—']
    if include_preferred_contact_method and profile and profile.preferred_contact_method:
        parts.append(
            f'предпочтительный способ связи: {profile.preferred_contact_method}',
        )
    return ' / '.join(p for p in parts if p)


def _customer_display_name(client) -> str:
    profile = getattr(client, 'client_profile', None)
    if not profile:
        return _client_full_name(client)

    if profile.client_kind == profile.CLIENT_KIND_COMPANY:
        details = getattr(profile, 'company_details', None)
        company_name = getattr(details, 'company_name', None) if details else None
        if company_name:
            return company_name
        first_name = getattr(profile, 'first_name', None)
        last_name = getattr(profile, 'last_name', None)
        if first_name and (not last_name or last_name == 'Компания'):
            return first_name

    return _client_full_name(client)


def _deal_owner_relations(deal):
    prop = getattr(deal, 'property', None)
    if not prop or not getattr(prop, 'pk', None):
        return []
    cache = getattr(prop, '_prefetched_objects_cache', {})
    if 'owners' in cache:
        return list(prop.owners.all())
    return list(
        prop.owners.select_related(
            'client_profile__user',
            'client_profile__individual_details',
            'client_profile__company_details',
        ).all()
    )


def _build_customer_entries(deal) -> tuple[list[dict], bool]:
    participant_entries = _build_participant_entries(
        deal,
        role_codes={'buyer', 'tenant'},
        default_label='Заказчик',
    )
    if participant_entries:
        return participant_entries, len(participant_entries) > 1

    client = getattr(deal, 'client', None)
    if client:
        return [
            {
                'label': 'Заказчик',
                'name': _client_full_name(client),
                'requisites_label': _client_requisites_label(client),
                'requisites_line': _client_requisites_line(client),
                'contact_line': _client_contact_line(client),
            },
        ], False

    return [], False


def _build_owner_entries(deal) -> list[dict]:
    participant_entries = _build_participant_entries(
        deal,
        role_codes={'seller', 'landlord'},
        default_label='Сторона объекта',
    )
    if participant_entries:
        return participant_entries

    owners = _deal_owner_relations(deal)
    if not owners:
        return []

    entries = []
    total = len(owners)
    for index, owner in enumerate(owners, start=1):
        profile = getattr(owner, 'client_profile', None)
        user = getattr(profile, 'user', None) if profile else None
        if not user:
            continue
        label = 'Собственник' if total == 1 else f'Собственник {index}'
        share = ''
        if total > 1 and owner.ownership_share not in (None, ''):
            share = _format_decimal(owner.ownership_share)
        if share:
            label = f'{label} ({share}%)'
        entries.append(
            {
                'label': label,
                'name': _customer_display_name(user),
                'requisites_label': _client_requisites_label(user),
                'requisites_line': _client_requisites_line(user),
                'contact_line': _client_contact_line(
                    user,
                    include_preferred_contact_method=False,
                ),
            },
        )
    return entries


def _build_participant_entries(deal, *, role_codes: set[str], default_label: str) -> list[dict]:
    participants = list(
        deal.participants.select_related(
            'client_profile__user',
            'client_profile__individual_details',
            'client_profile__company_details',
            'role',
        ).all()
    )
    if not participants:
        return []

    matched = [item for item in participants if getattr(getattr(item, 'role', None), 'code', None) in role_codes]
    if not matched:
        return []

    entries = []
    total = len(matched)
    for index, participant in enumerate(matched, start=1):
        profile = getattr(participant, 'client_profile', None)
        user = getattr(profile, 'user', None) if profile else None
        if not user:
            continue
        role_name = getattr(participant.role, 'name', None) or default_label
        label = role_name if total == 1 else f'{role_name} {index}'
        entries.append(
            {
                'label': label,
                'name': _customer_display_name(user),
                'requisites_label': _client_requisites_label(user),
                'requisites_line': _client_requisites_line(user),
                'contact_line': _client_contact_line(
                    user,
                    include_preferred_contact_method=False,
                ),
            },
        )
    return entries


def _customer_intro_text(entries, *, owner_mode: bool) -> str:
    names = ', '.join(entry['name'] for entry in entries if entry.get('name'))
    if owner_mode and len(entries) > 1:
        return f'Заказчик: {names}, далее совместно именуемые Заказчик.'
    return f'Заказчик: {names}.'


def _customer_info_rows(entries) -> list[tuple[str, str]]:
    rows = []
    for entry in entries:
        rows.append(
            (
                entry['label'],
                '\n'.join([
                    entry['name'],
                    f'{entry["requisites_label"]}: {entry["requisites_line"]}',
                    f'Контакты: {entry["contact_line"]}',
                ]),
            ),
        )
    return rows


def _customer_signature_markup(entry, *, include_contacts: bool) -> str:
    signature_line = '______________________________'
    parts = [
        f'<b>{_paragraph_text(entry["label"])}</b><br/>',
        f'{_paragraph_text(entry["name"])}<br/>',
    ]
    if include_contacts:
        parts.append(f'Контакты: {_paragraph_text(entry["contact_line"])}<br/>')
    parts.append(
        (
            f'{_paragraph_text(entry["requisites_label"])}: '
            f'{_paragraph_text(entry["requisites_line"])}<br/><br/>'
            f'{signature_line}<br/>'
            f'<font size="8">подпись / расшифровка</font>'
        ),
    )
    return ''.join(parts)


def _agency_name() -> str:
    return getattr(settings, 'AGENCY_NAME', 'Агентство недвижимости')


def _agency_legal_name() -> str:
    return _setting('AGENCY_LEGAL_NAME', _agency_name())


def _agency_signatory_name(agent) -> str:
    return _setting('AGENCY_SIGNATORY_NAME', _agent_full_name(agent))


def _agency_signatory_title(agent) -> str:
    return _setting('AGENCY_SIGNATORY_TITLE', _agent_position(agent))


def _agency_signatory_basis() -> str:
    return _setting(
        'AGENCY_SIGNATORY_BASIS',
        'внутренних документов Исполнителя',
    )


def _agency_address() -> str:
    return _setting('AGENCY_ADDRESS', 'адрес указывается при подписании')


def _agency_phone() -> str:
    return _setting('AGENCY_PHONE')


def _agency_contact_line() -> str:
    parts = []
    phone = _agency_phone()
    reply_to = getattr(settings, 'AGENCY_REPLY_TO', '') or getattr(
        settings,
        'DEFAULT_FROM_EMAIL',
        '',
    )
    public_url = getattr(settings, 'AGENCY_PUBLIC_URL', '')
    if phone:
        parts.append(phone)
    if reply_to:
        parts.append(reply_to)
    if public_url:
        parts.append(public_url)
    return ' / '.join(parts) or 'контакты уточняются при подписании'


def _agency_requisites_lines() -> list[str]:
    fields = [
        ('Адрес', _agency_address()),
        ('Телефон', _agency_phone()),
        ('Email', _setting('AGENCY_REPLY_TO', _setting('DEFAULT_FROM_EMAIL'))),
        ('ИНН', _setting('AGENCY_INN')),
        ('КПП', _setting('AGENCY_KPP')),
        ('ОГРН', _setting('AGENCY_OGRN')),
    ]
    lines = [f'{label}: {value}' for label, value in fields if value and value != '—']

    bank_details = getattr(settings, 'AGENCY_BANK_DETAILS', '') or ''
    if bank_details:
        normalized_bank_details = str(bank_details).replace(';', '\n')
        for line in normalized_bank_details.splitlines():
            normalized = line.strip()
            if normalized:
                lines.append(normalized)

    public_url = getattr(settings, 'AGENCY_PUBLIC_URL', '')
    if public_url:
        lines.append(f'Сайт: {public_url}')
    return lines or ['Реквизиты уточняются при подписании']


def _join_lines(lines: Iterable[str]) -> str:
    return '<br/>'.join(_paragraph_text(line) for line in lines if line)


def _deal_transaction_label(deal) -> str:
    code = getattr(deal.operation_type, 'code', None)
    if code == 'sale':
        return 'купли-продажи'
    if code == 'rent':
        return 'аренды'
    return 'сделки'


def _deal_result_label(deal) -> str:
    code = getattr(deal.operation_type, 'code', None)
    if code == 'sale':
        return 'заключения сделки купли-продажи'
    if code == 'rent':
        return 'заключения договора аренды'
    return 'завершения сделки'


def _deal_subject(deal) -> str:
    operation_name = deal.operation_type.name if deal.operation_type_id else 'сделка'
    property_title = deal.property.title or f'объект №{deal.property_id}'
    return (
        f'оказание информационно-консультационных и организационных услуг '
        f'по сопровождению {operation_name.lower()} объекта недвижимости '
        f'«{property_title}»'
    )


def _section_heading(text: str, style) -> Paragraph:
    return Paragraph(escape(text), style)


def _table_value(value, style, *, fallback: str = '—') -> Paragraph:
    if isinstance(value, Paragraph):
        return value
    return Paragraph(_paragraph_text(value, fallback), style)


def _info_table(rows, *, label_style, value_style, col_widths=None) -> Table:
    normalized = []
    for label, value in rows:
        normalized.append(
            [
                Paragraph(f'<b>{escape(_as_text(label, ""))}</b>', label_style),
                _table_value(value, value_style),
            ],
        )

    table = Table(
        normalized,
        colWidths=col_widths or [LABEL_WIDTH, VALUE_WIDTH],
        repeatRows=0,
        hAlign='LEFT',
    )
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), COLOR_TEXT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('LEFTPADDING', (1, 0), (1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return table


def _key_value_table(rows, styles) -> Table:
    return _info_table(
        rows,
        label_style=styles['label'],
        value_style=styles['table_value'],
    )


def _meta_header_table(deal, *, styles) -> Table:
    meta_left = Paragraph(escape(_deal_city(deal)), styles['meta_header_left'])
    meta_right = Paragraph(
        escape(f'Дата составления: {_format_date(deal.deal_date)}'),
        styles['meta_header_right'],
    )
    table = Table([[meta_left, meta_right]], colWidths=[CONTENT_WIDTH * 0.55, CONTENT_WIDTH * 0.45], hAlign='LEFT')
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return table


def _signature_table(deal, *, styles, customer_entries=None, owner_mode: bool = False) -> Table:
    signature = styles['signature']
    small = styles['signature_note']
    signature_line = '______________________________'
    left = Paragraph(
        (
            f'<b>Исполнитель</b><br/>'
            f'{_paragraph_text(_agency_legal_name())}<br/>'
            f'Подписант: {_paragraph_text(_agency_signatory_name(deal.agent))}<br/>'
            f'Должность: {_paragraph_text(_agency_signatory_title(deal.agent))}<br/>'
            f'Основание полномочий: {_paragraph_text(_agency_signatory_basis())}<br/>'
            f'{_join_lines(_agency_requisites_lines())}<br/><br/>'
            f'{signature_line}<br/>'
            f'<font size="8">{_paragraph_text(_agency_signatory_title(deal.agent))}</font>'
        ),
        signature,
    )
    entries = customer_entries
    if entries is None:
        entries, owner_mode = _build_customer_entries(deal)
    entries = entries or []
    right_entries = entries[:]
    if not right_entries and getattr(deal, 'client', None):
        right_entries = [
            {
                'label': 'Заказчик',
                'name': _client_full_name(deal.client),
                'requisites_label': _client_requisites_label(deal.client),
                'requisites_line': _client_requisites_line(deal.client),
                'contact_line': _client_contact_line(deal.client),
            },
        ]

    rows = []
    if right_entries:
        if owner_mode and len(right_entries) > 1:
            rows.append([
                left,
                Paragraph(_customer_signature_markup(right_entries[0], include_contacts=False), signature),
            ])
            for entry in right_entries[1:]:
                rows.append([
                    Paragraph(_customer_signature_markup(entry, include_contacts=False), signature),
                    '',
                ])
        else:
            rows.append([
                left,
                Paragraph(_customer_signature_markup(right_entries[0], include_contacts=True), signature),
            ])

    table = Table(
        rows,
        colWidths=[(CONTENT_WIDTH - 10) / 2, (CONTENT_WIDTH - 10) / 2],
        hAlign='LEFT',
    )
    table_style = [
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 10),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]
    if owner_mode and len(right_entries) > 1:
        for row_index in range(1, len(rows)):
            table_style.extend([
                ('SPAN', (0, row_index), (1, row_index)),
                ('LEFTPADDING', (0, row_index), (0, row_index), 0),
                ('RIGHTPADDING', (0, row_index), (0, row_index), 0),
            ])
    table.setStyle(TableStyle(table_style))
    note = Paragraph(
        (
            f'Документ сформирован автоматически CRM {_paragraph_text(_agency_name())} '
            f'{timezone.now():%d.%m.%Y %H:%M}. Для подписания допускается печать '
            f'и дополнение реквизитов в бумажном экземпляре.'
        ),
        small,
    )
    return KeepTogether([table, Spacer(1, 6), note])


def _draw_page_chrome(canvas, doc, deal) -> None:
    canvas.saveState()
    canvas.setFillColor(COLOR_MUTED)
    canvas.setFont(FONT_REGULAR, 8)
    canvas.drawString(doc.leftMargin, 7.5 * mm, _agency_name())
    canvas.drawRightString(
        PAGE_WIDTH - doc.rightMargin,
        7.5 * mm,
        f'Договор {deal.deal_number} • стр. {canvas.getPageNumber()}',
    )
    canvas.restoreState()


def render_contract_pdf(deal) -> ContentFile:
    """Возвращает PDF-договор в ``ContentFile``."""
    _ensure_fonts_registered()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN_LEFT,
        rightMargin=PAGE_MARGIN_RIGHT,
        topMargin=PAGE_MARGIN_TOP,
        bottomMargin=PAGE_MARGIN_BOTTOM,
        pageCompression=0,
        title=f'Договор по сделке {deal.deal_number}',
        author=_agency_name(),
        subject='Договор оказания риэлторских услуг',
    )

    base = getSampleStyleSheet()['BodyText']
    styles = {
        'body': ParagraphStyle(
            'ContractBody',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=10.2,
            leading=13.6,
            textColor=COLOR_TEXT,
            alignment=TA_JUSTIFY,
            firstLineIndent=14,
            spaceAfter=2.5,
        ),
        'clause': ParagraphStyle(
            'ContractClause',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=10.1,
            leading=13.5,
            textColor=COLOR_TEXT,
            alignment=TA_JUSTIFY,
            firstLineIndent=0,
            spaceAfter=2.2,
        ),
        'table_value': ParagraphStyle(
            'ContractTableValue',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=9.8,
            leading=12.2,
            textColor=COLOR_TEXT,
            alignment=TA_LEFT,
            firstLineIndent=0,
            spaceAfter=0,
        ),
        'label': ParagraphStyle(
            'ContractLabel',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=9.2,
            leading=11.2,
            textColor=COLOR_TEXT,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        'small': ParagraphStyle(
            'ContractSmall',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=7.8,
            leading=9.6,
            textColor=COLOR_MUTED,
        ),
        'meta_header_left': ParagraphStyle(
            'ContractMetaHeaderLeft',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=11,
            textColor=COLOR_MUTED,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        'meta_header_right': ParagraphStyle(
            'ContractMetaHeaderRight',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=11,
            textColor=COLOR_MUTED,
            alignment=TA_RIGHT,
            spaceAfter=0,
        ),
        'meta': ParagraphStyle(
            'ContractMeta',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=11.2,
            textColor=COLOR_MUTED,
            alignment=TA_CENTER,
            spaceAfter=0.5,
        ),
        'title': ParagraphStyle(
            'ContractTitle',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=14.2,
            leading=16.6,
            textColor=COLOR_TEXT,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        'subtitle': ParagraphStyle(
            'ContractSubtitle',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=10.1,
            leading=12.2,
            textColor=COLOR_TEXT,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        'section': ParagraphStyle(
            'ContractSection',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=10.8,
            leading=12.8,
            textColor=COLOR_TEXT,
            spaceBefore=7,
            spaceAfter=3,
        ),
        'signature': ParagraphStyle(
            'ContractSignature',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=9.8,
            leading=12.4,
            textColor=COLOR_TEXT,
            alignment=TA_LEFT,
            firstLineIndent=0,
            spaceAfter=0,
        ),
        'signature_note': ParagraphStyle(
            'ContractSignatureNote',
            parent=base,
            fontName=FONT_ITALIC,
            fontSize=7.5,
            leading=9.2,
            textColor=COLOR_MUTED,
            alignment=TA_LEFT,
            firstLineIndent=0,
            spaceAfter=0,
        ),
    }

    operation_name = deal.operation_type.name if deal.operation_type_id else 'Сделка'
    property_obj = deal.property
    deal_transaction_label = _deal_transaction_label(deal)
    deal_result_label = _deal_result_label(deal)
    clause_style = styles['clause']

    story = []

    story.extend([
        _meta_header_table(deal, styles=styles),
        Spacer(1, 8),
        Paragraph('ДОГОВОР ОКАЗАНИЯ РИЭЛТОРСКИХ УСЛУГ', styles['title']),
        Paragraph(f'№ {escape(deal.deal_number)}', styles['subtitle']),
        Paragraph(_paragraph_text(_deal_subject(deal)), styles['meta']),
        Spacer(1, 7),
    ])

    customer_entries, owner_mode = _build_customer_entries(deal)
    owner_entries = _build_owner_entries(deal)

    story.append(_section_heading('1. Стороны договора', styles['section']))
    story.append(
        Paragraph(
            (
                f'Исполнитель: {_paragraph_text(_agency_legal_name())}, '
                f'в лице {_paragraph_text(_agency_signatory_name(deal.agent))}, '
                f'действующего на основании {_paragraph_text(_agency_signatory_basis())}. '
                f'{_paragraph_text(_customer_intro_text(customer_entries, owner_mode=owner_mode))} '
                f'Стороны подтверждают намерение организовать и сопровождать '
                f'подготовку и совершение {deal_transaction_label} по объекту '
                f'недвижимости на условиях настоящего договора.'
            ),
            styles['body'],
        ),
    )
    story.append(
        _info_table(
            [
                ('Исполнитель', _agency_legal_name()),
                ('Подписант Исполнителя', _agency_signatory_name(deal.agent)),
                ('Должность / роль', _agency_signatory_title(deal.agent)),
                ('Основание полномочий', _agency_signatory_basis()),
                ('Контакты исполнителя', _agency_contact_line()),
            ]
            + _customer_info_rows(customer_entries)
            + _customer_info_rows(owner_entries),
            label_style=styles['label'],
            value_style=styles['table_value'],
        ),
    )

    story.append(
        _section_heading('2. Предмет договора', styles['section']),
    )
    story.extend([
        Paragraph(
            (
                'Исполнитель обязуется оказать Заказчику информационно-'
                'консультационные, организационные и сопровождающие услуги, '
                'необходимые для подготовки, согласования и проведения '
                f'{deal_transaction_label} '
                'с объектом недвижимости, указанным в разделе 3 настоящего '
                'договора, а Заказчик обязуется принять и оплатить такие услуги.'
            ),
            styles['body'],
        ),
        Paragraph(
            (
                'Оказание услуг включает анализ параметров сделки, коммуникацию '
                'с участниками, организацию показов и переговоров, проверку '
                'доступного комплекта документов, подготовку проекта договорного '
                f'комплекта и сопровождение согласования до момента {deal_result_label}.'
            ),
            styles['body'],
        ),
    ])
    if deal.request_id:
        story.append(
            Paragraph(
                (
                    f'Основание для сопровождения: клиентская заявка '
                    f'№ {deal.request_id}.'
                ),
                styles['body'],
            ),
        )

    story.append(
        _section_heading('3. Сведения об объекте и параметрах сделки', styles['section']),
    )
    property_rows = [
        ('Объект', property_obj.title or f'Объект №{property_obj.pk}'),
        ('Адрес объекта', _property_address(property_obj)),
        ('Тип операции', operation_name),
        ('Финальная стоимость сделки', _money(deal.price_final)),
        ('Стоимость прописью', _money_words(deal.price_final)),
        ('Статус сделки', getattr(deal.status, 'name', '—')),
    ]
    if property_obj.area_total:
        property_rows.append(('Общая площадь', _format_decimal(property_obj.area_total, ' м²')))
    if property_obj.rooms_count:
        property_rows.append(('Количество комнат', property_obj.rooms_count))
    if property_obj.floor_number and property_obj.total_floors:
        property_rows.append(
            ('Этаж / этажность', f'{property_obj.floor_number} / {property_obj.total_floors}'),
        )
    story.append(
        _info_table(
            property_rows,
            label_style=styles['label'],
            value_style=styles['table_value'],
        ),
    )

    story.append(
        _section_heading('4. Порядок оказания услуг', styles['section']),
    )
    workflow_points = [
        f'4.1. Исполнитель собирает и уточняет параметры {deal_transaction_label}, согласует ключевые условия и перечень необходимых действий.',
        '4.2. Исполнитель организует коммуникацию между сторонами сделки, включая переговоры, показы объекта и согласование даты подписания документов.',
        '4.3. Исполнитель помогает сформировать и проверить доступный комплект документов по объекту и по участникам сделки в пределах переданных ему сведений.',
        f'4.4. Исполнитель сопровождает подготовку проекта договора и связанных документов, а также информирует Заказчика о ходе оказания услуг до момента {deal_result_label}.',
    ]
    for point in workflow_points:
        story.append(Paragraph(point, clause_style))

    story.append(
        _section_heading('5. Стоимость услуг и порядок расчётов', styles['section']),
    )
    commission_percent = (
        f'{_format_decimal(deal.commission_percent)} %'
        if deal.commission_percent not in (None, '')
        else '—'
    )
    story.append(
        _info_table(
            [
                ('Размер вознаграждения', commission_percent),
                ('Сумма вознаграждения', _money(deal.commission_amount)),
                ('Сумма вознаграждения прописью', _money_words(deal.commission_amount)),
                ('Стоимость объекта', _money(deal.price_final)),
                (
                    'Порядок оплаты',
                    'определяется Сторонами на основании настоящего договора и подтверждается при завершении сделки',
                ),
            ],
            label_style=styles['label'],
            value_style=styles['table_value'],
        ),
    )
    story.append(
        Paragraph(
            (
                'В случае изменения согласованных параметров сделки Стороны вправе '
                'оформить письменное дополнение либо зафиксировать новые условия '
                'в отдельном согласовании.'
            ),
            styles['body'],
        ),
    )

    story.append(
        _section_heading('6. Права и обязанности сторон', styles['section']),
    )
    rights_block = [
        '6.1. Исполнитель обязан действовать добросовестно, информировать Заказчика о существенных этапах сопровождения и обеспечивать надлежащее оформление сопровождающих материалов.',
        '6.2. Заказчик обязан предоставлять достоверные сведения, своевременно отвечать на запросы Исполнителя и участвовать в согласовании условий сделки.',
        '6.3. Стороны обязуются не допускать действий, способных сорвать подготовленную сделку либо исказить существенные условия договорённостей.',
    ]
    for point in rights_block:
        story.append(Paragraph(point, clause_style))

    story.append(
        _section_heading('7. Ответственность, срок действия и прочие условия', styles['section']),
    )
    final_points = [
        '7.1. Настоящий договор вступает в силу с момента подписания Сторонами и действует до полного исполнения обязательств либо до прекращения по соглашению Сторон.',
        '7.2. Заказчик вправе отказаться от исполнения договора при условии оплаты фактически оказанных услуг и подтверждённых расходов Исполнителя, если иное не согласовано Сторонами отдельно.',
        '7.3. Исполнитель вправе отказаться от исполнения договора при условии полного возмещения Заказчику подтверждённых убытков, причинённых таким отказом, если иное не следует из существа обязательства.',
        '7.4. Все разногласия по договору Стороны стремятся урегулировать путём переговоров; при недостижении соглашения спор разрешается в порядке, установленном законодательством Российской Федерации.',
        '7.5. Во всём, что не урегулировано настоящим договором, Стороны руководствуются действующим законодательством Российской Федерации.',
    ]
    for point in final_points:
        story.append(Paragraph(point, clause_style))

    if deal.notes:
        story.append(_section_heading('8. Особые условия', styles['section']))
        story.append(Paragraph(_paragraph_text(deal.notes), styles['table_value']))

    story.extend([
        Spacer(1, 10),
        _section_heading('9. Реквизиты и подписи сторон', styles['section']),
        _signature_table(
            deal,
            styles=styles,
            customer_entries=customer_entries,
            owner_mode=owner_mode,
        ),
    ])

    doc.build(
        story,
        onFirstPage=lambda canvas, page_doc: _draw_page_chrome(canvas, page_doc, deal),
        onLaterPages=lambda canvas, page_doc: _draw_page_chrome(canvas, page_doc, deal),
    )
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return ContentFile(pdf_bytes, name=f'contract-{deal.deal_number}.pdf')


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()['BodyText']
    return {
        'body': ParagraphStyle(
            'body',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=14,
            alignment=TA_JUSTIFY,
            textColor=COLOR_TEXT,
        ),
        'clause': ParagraphStyle(
            'clause',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=14,
            alignment=TA_JUSTIFY,
            firstLineIndent=8 * mm,
            spaceAfter=2,
            textColor=COLOR_TEXT,
        ),
        'table_value': ParagraphStyle(
            'table_value',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=13,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
        ),
        'label': ParagraphStyle(
            'label',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=9.5,
            leading=12,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
        ),
        'small': ParagraphStyle(
            'small',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=10,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
        ),
        'meta_header_left': ParagraphStyle(
            'meta_header_left',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
        ),
        'meta_header_right': ParagraphStyle(
            'meta_header_right',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=9,
            leading=11,
            alignment=TA_RIGHT,
            textColor=COLOR_TEXT,
        ),
        'meta': ParagraphStyle(
            'meta',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=10,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
        ),
        'title': ParagraphStyle(
            'title',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            textColor=COLOR_TEXT,
            spaceAfter=2,
        ),
        'subtitle': ParagraphStyle(
            'subtitle',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=COLOR_TEXT,
        ),
        'section': ParagraphStyle(
            'section',
            parent=base,
            fontName=FONT_BOLD,
            fontSize=11.5,
            leading=14,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
            spaceBefore=4,
            spaceAfter=4,
        ),
        'signature': ParagraphStyle(
            'signature',
            parent=base,
            fontName=FONT_REGULAR,
            fontSize=9.5,
            leading=12,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
        ),
        'signature_note': ParagraphStyle(
            'signature_note',
            parent=base,
            fontName=FONT_ITALIC,
            fontSize=8.5,
            leading=10,
            alignment=TA_CENTER,
            textColor=COLOR_TEXT,
        ),
    }


def render_property_summary_pdf(property_obj) -> ContentFile:
    _ensure_fonts_registered()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN_LEFT,
        rightMargin=PAGE_MARGIN_RIGHT,
        topMargin=PAGE_MARGIN_TOP,
        bottomMargin=PAGE_MARGIN_BOTTOM,
        title=f'Карточка объекта #{property_obj.pk}',
        author=_agency_name(),
    )
    styles = _pdf_styles()
    story = [
        Paragraph('Карточка объекта недвижимости', styles['title']),
        Spacer(1, 4 * mm),
        Paragraph(_paragraph_text(property_obj.title or f'Объект #{property_obj.pk}'), styles['subtitle']),
        Spacer(1, 4 * mm),
        _section_heading('Основная информация', styles['section']),
        _key_value_table([
            ('ID объекта', property_obj.pk),
            ('Тип операции', getattr(getattr(property_obj, 'operation_type', None), 'name', None)),
            ('Статус', getattr(getattr(property_obj, 'status', None), 'name', None)),
            ('Тип объекта', getattr(getattr(property_obj, 'property_type_ref', None), 'name', None)),
            ('Адрес', _property_address(property_obj)),
            ('Стоимость', _money(getattr(property_obj, 'price', None))),
            ('Площадь', _format_decimal(getattr(property_obj, 'area_total', None), ' м²')),
            ('Комнат', getattr(property_obj, 'rooms_count', None)),
            ('Этаж', getattr(property_obj, 'floor_number', None)),
            ('Кадастровый номер', getattr(property_obj, 'cadastral_number', None)),
            ('Опубликован', 'Да' if getattr(property_obj, 'is_published', False) else 'Нет'),
            ('Создан', _format_date(getattr(property_obj, 'created_at', None))),
        ], styles),
    ]

    details = getattr(property_obj, 'details', None)
    if details is not None:
        story.extend([
            Spacer(1, 4 * mm),
            _section_heading('Характеристики помещения', styles['section']),
            _key_value_table([
                ('Жилая площадь', _format_decimal(getattr(details, 'living_area', None), ' м²')),
                ('Площадь кухни', _format_decimal(getattr(details, 'kitchen_area', None), ' м²')),
                ('Высота потолков', _format_decimal(getattr(details, 'ceiling_height', None), ' м')),
                ('Балконы', getattr(details, 'balcony_count', None)),
                ('Санузлы', getattr(details, 'bathroom_count', None)),
                ('Тип санузла', getattr(getattr(details, 'bathroom_type', None), 'name', None)),
                ('Ремонт', getattr(getattr(details, 'renovation_type', None), 'name', None)),
                ('Спальни', getattr(details, 'bedrooms_count', None)),
                ('Этажей в помещении', getattr(details, 'floors_count', None)),
                ('Площадь участка', _format_decimal(getattr(details, 'land_area', None), ' м²')),
            ], styles),
        ])

    commercial = getattr(property_obj, 'commercial_details', None)
    if commercial is not None:
        story.extend([
            Spacer(1, 4 * mm),
            _section_heading('Коммерческие параметры', styles['section']),
            _key_value_table([
                ('Тип коммерции', getattr(getattr(commercial, 'commercial_type', None), 'name', None)),
                ('Полезная площадь', _format_decimal(getattr(commercial, 'usable_area', None), ' м²')),
                ('Высота потолков', _format_decimal(getattr(commercial, 'ceiling_height', None), ' м')),
                ('Нагрузка на пол', _format_decimal(getattr(commercial, 'floor_load', None), ' кг/м²')),
                ('Электромощность', _format_decimal(getattr(commercial, 'electric_power_kw', None), ' кВт')),
                ('Отдельный вход', 'Да' if getattr(commercial, 'has_separate_entrance', False) else 'Нет'),
                ('Витринные окна', 'Да' if getattr(commercial, 'has_display_windows', False) else 'Нет'),
                ('Первая линия', 'Да' if getattr(commercial, 'is_first_line', False) else 'Нет'),
                ('Парковочные места', getattr(commercial, 'parking_spaces', None)),
            ], styles),
        ])

    house = getattr(property_obj, 'house', None)
    building = getattr(house, 'building_details', None) if house is not None else None
    if building is not None:
        story.extend([
            Spacer(1, 4 * mm),
            _section_heading('Параметры здания', styles['section']),
            _key_value_table([
                ('Год постройки', getattr(building, 'year_built', None)),
                ('Этажность дома', getattr(building, 'total_floors', None)),
                ('Материал', getattr(getattr(building, 'building_material', None), 'name', None)),
                ('Лифты', getattr(building, 'elevators_count', None)),
            ], styles),
        ])

    story.extend([
        Spacer(1, 4 * mm),
        _section_heading('Описание', styles['section']),
        Paragraph(
            _paragraph_text(getattr(property_obj, 'description', None), 'Описание не заполнено.'),
            styles['table_value'],
        ),
    ])

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return ContentFile(pdf_bytes, name=f'property-{property_obj.pk}.pdf')
