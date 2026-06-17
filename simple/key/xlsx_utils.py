# -*- coding: utf-8 -*-
"""Минимальный XLSX reader/writer без внешних зависимостей."""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from io import BytesIO
from typing import Iterable
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
DOC_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CORE_NS = 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
DC_NS = 'http://purl.org/dc/elements/1.1/'
DCTERMS_NS = 'http://purl.org/dc/terms/'
XML_NS = 'http://www.w3.org/XML/1998/namespace'

INVALID_XML_CHARS_RE = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]')
INVALID_SHEET_NAME_RE = re.compile(r'[\[\]:*?/\\]')
CELL_REF_RE = re.compile(r'([A-Z]+)(\d+)')


@dataclass(frozen=True)
class WorkbookSheet:
    name: str
    rows: tuple[tuple[object, ...], ...]
    header_rows: int = 1

    @classmethod
    def from_rows(
        cls,
        name: str,
        rows: Iterable[Iterable[object]],
        *,
        header_rows: int = 1,
    ) -> 'WorkbookSheet':
        return cls(
            name=name,
            rows=tuple(tuple(row) for row in rows),
            header_rows=header_rows,
        )


def _q(namespace: str, tag: str) -> str:
    return f'{{{namespace}}}{tag}'


def _safe_text(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat(sep=' ')
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    return INVALID_XML_CHARS_RE.sub('', text)


def _sanitize_sheet_name(name: str, *, index: int) -> str:
    normalized = INVALID_SHEET_NAME_RE.sub('_', (name or '').strip())[:31]
    if not normalized:
        return f'Sheet{index}'
    return normalized


def _column_name(index: int) -> str:
    letters: list[str] = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return ''.join(reversed(letters))


def _column_index_from_ref(cell_ref: str) -> int:
    match = CELL_REF_RE.fullmatch(cell_ref or '')
    if not match:
        return 0
    letters = match.group(1)
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - 64)
    return max(value - 1, 0)


def _column_widths(rows: tuple[tuple[object, ...], ...]) -> list[int]:
    widths: list[int] = []
    for row in rows:
        for index, value in enumerate(row):
            text = _safe_text(value)
            width = min(max(len(text) + 2, 10), 60)
            if index >= len(widths):
                widths.append(width)
            else:
                widths[index] = max(widths[index], width)
    return widths


def _worksheet_xml(sheet: WorkbookSheet) -> str:
    rows = sheet.rows
    widths = _column_widths(rows)
    cols = ''.join(
        (
            f'<col min="{index}" max="{index}" '
            f'width="{width}" customWidth="1"/>'
        )
        for index, width in enumerate(widths, start=1)
    )
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{MAIN_NS}">',
    ]
    if cols:
        parts.append(f'<cols>{cols}</cols>')
    parts.append('<sheetData>')
    for row_index, row in enumerate(rows, start=1):
        parts.append(f'<row r="{row_index}">')
        for column_index, value in enumerate(row, start=1):
            cell_ref = f'{_column_name(column_index)}{row_index}'
            style = ' s="1"' if row_index <= sheet.header_rows else ''
            if isinstance(value, bool):
                parts.append(
                    f'<c r="{cell_ref}"{style} t="b"><v>{1 if value else 0}</v></c>',
                )
                continue
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                parts.append(f'<c r="{cell_ref}"{style}><v>{value}</v></c>')
                continue
            text = escape(_safe_text(value))
            parts.append(
                f'<c r="{cell_ref}"{style} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>',
            )
        parts.append('</row>')
    parts.append('</sheetData></worksheet>')
    return ''.join(parts)


def _content_types_xml(sheet_count: int) -> str:
    overrides = ''.join(
        (
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'{overrides}'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '</Types>'
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/>'
        '</Relationships>'
    )


def _workbook_xml(sheets: tuple[WorkbookSheet, ...]) -> str:
    sheet_entries = ''.join(
        (
            f'<sheet name="{escape(sheet.name)}" sheetId="{index}" '
            f'r:id="rId{index}"/>'
        )
        for index, sheet in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{DOC_REL_NS}">'
        f'<sheets>{sheet_entries}</sheets>'
        '</workbook>'
    )


def _workbook_relationships_xml(sheet_count: int) -> str:
    relationships = ''.join(
        (
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
        for index in range(1, sheet_count + 1)
    )
    relationships += (
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">{relationships}</Relationships>'
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{MAIN_NS}">'
        '<fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )


def _core_properties_xml() -> str:
    created = datetime.now(dt_timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{CORE_NS}" xmlns:dc="{DC_NS}" '
        f'xmlns:dcterms="{DCTERMS_NS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>CRM Export</dc:title>'
        '<dc:creator>Codex</dc:creator>'
        '<cp:lastModifiedBy>Codex</cp:lastModifiedBy>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
        '</cp:coreProperties>'
    )


def _app_properties_xml(sheets: tuple[WorkbookSheet, ...]) -> str:
    titles = ''.join(f'<vt:lpstr>{escape(sheet.name)}</vt:lpstr>' for sheet in sheets)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Microsoft Excel</Application>'
        f'<TitlesOfParts><vt:vector size="{len(sheets)}" baseType="lpstr">{titles}</vt:vector></TitlesOfParts>'
        '</Properties>'
    )


def build_xlsx_bytes(sheets: Iterable[WorkbookSheet]) -> bytes:
    normalized = tuple(
        WorkbookSheet(
            name=_sanitize_sheet_name(sheet.name, index=index),
            rows=sheet.rows,
        )
        for index, sheet in enumerate(sheets, start=1)
    )
    if not normalized:
        raise ValueError('At least one worksheet is required.')

    buffer = BytesIO()
    with ZipFile(buffer, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', _content_types_xml(len(normalized)))
        archive.writestr('_rels/.rels', _root_relationships_xml())
        archive.writestr('docProps/core.xml', _core_properties_xml())
        archive.writestr('docProps/app.xml', _app_properties_xml(normalized))
        archive.writestr('xl/workbook.xml', _workbook_xml(normalized))
        archive.writestr('xl/styles.xml', _styles_xml())
        archive.writestr('xl/_rels/workbook.xml.rels', _workbook_relationships_xml(len(normalized)))
        for index, sheet in enumerate(normalized, start=1):
            archive.writestr(
                f'xl/worksheets/sheet{index}.xml',
                _worksheet_xml(sheet),
            )
    return buffer.getvalue()


def _read_source_bytes(source) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    raw = source.read()
    if hasattr(source, 'seek'):
        source.seek(0)
    return raw


def _shared_strings_map(archive: ZipFile) -> list[str]:
    if 'xl/sharedStrings.xml' not in archive.namelist():
        return []
    root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
    shared_strings: list[str] = []
    for item in root.findall(_q(MAIN_NS, 'si')):
        text_parts = [node.text or '' for node in item.iterfind(f'.//{_q(MAIN_NS, "t")}')]
        shared_strings.append(''.join(text_parts))
    return shared_strings


def _worksheet_target(archive: ZipFile, *, sheet_name: str | None = None) -> str:
    workbook_root = ET.fromstring(archive.read('xl/workbook.xml'))
    rels_root = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    relationships = {
        rel.attrib['Id']: rel.attrib['Target']
        for rel in rels_root.findall(_q(PKG_REL_NS, 'Relationship'))
    }
    sheets = workbook_root.find(_q(MAIN_NS, 'sheets'))
    if sheets is None:
        raise ValueError('Workbook does not contain sheets.')
    selected = None
    for sheet in sheets.findall(_q(MAIN_NS, 'sheet')):
        if sheet_name is None or sheet.attrib.get('name') == sheet_name:
            selected = sheet
            break
    if selected is None:
        raise ValueError('Requested sheet is not present in workbook.')
    rel_id = selected.attrib.get(_q(DOC_REL_NS, 'id'))
    if not rel_id or rel_id not in relationships:
        raise ValueError('Worksheet relation is missing.')
    target = relationships[rel_id]
    if target.startswith('/'):
        return target.lstrip('/')
    return posixpath.normpath(posixpath.join('xl', target))


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get('t')
    if cell_type == 'inlineStr':
        return ''.join(
            node.text or ''
            for node in cell.iterfind(f'.//{_q(MAIN_NS, "t")}')
        )
    value_node = cell.find(_q(MAIN_NS, 'v'))
    value = value_node.text if value_node is not None else ''
    if cell_type == 's':
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ''
    if cell_type == 'b':
        return 'TRUE' if value == '1' else 'FALSE'
    return value or ''


def load_xlsx_rows(source, *, sheet_name: str | None = None) -> list[list[str]]:
    raw = _read_source_bytes(source)
    with ZipFile(BytesIO(raw)) as archive:
        worksheet_path = _worksheet_target(archive, sheet_name=sheet_name)
        shared_strings = _shared_strings_map(archive)
        worksheet_root = ET.fromstring(archive.read(worksheet_path))

    sheet_data = worksheet_root.find(_q(MAIN_NS, 'sheetData'))
    if sheet_data is None:
        return []

    rows: list[list[str]] = []
    for row in sheet_data.findall(_q(MAIN_NS, 'row')):
        cells: dict[int, str] = {}
        max_index = -1
        for cell in row.findall(_q(MAIN_NS, 'c')):
            ref = cell.attrib.get('r', '')
            index = _column_index_from_ref(ref)
            max_index = max(max_index, index)
            cells[index] = _cell_text(cell, shared_strings)
        if max_index < 0:
            rows.append([])
            continue
        values = [''] * (max_index + 1)
        for index, value in cells.items():
            values[index] = value
        while values and values[-1] == '':
            values.pop()
        rows.append(values)
    return rows
