# -*- coding: utf-8 -*-
"""Утилиты полного резервного копирования базы данных."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections
from django.utils import timezone

from . import models


OPTION_ENV_MAP = {
    'application_name': 'PGAPPNAME',
    'options': 'PGOPTIONS',
    'passfile': 'PGPASSFILE',
    'service': 'PGSERVICE',
    'sslcert': 'PGSSLCERT',
    'sslcrl': 'PGSSLCRL',
    'sslkey': 'PGSSLKEY',
    'sslmode': 'PGSSLMODE',
    'sslrootcert': 'PGSSLROOTCERT',
}


class DatabaseBackupError(RuntimeError):
    """Ошибка подготовки или формирования резервной копии."""


@dataclass(frozen=True)
class DatabaseBackupOverview:
    engine_label: str
    database_name: str
    location_label: str
    format_label: str
    tool_label: str
    available: bool
    unavailable_reason: str = ''


def _is_postgresql_engine(engine: str) -> bool:
    return 'postgresql' in (engine or '').lower()


def _resolve_pg_dump_path() -> str | None:
    configured_path = os.getenv('PG_DUMP_PATH', '').strip()
    if configured_path:
        candidate = Path(configured_path).expanduser()
        if candidate.is_file():
            return str(candidate)
        return None

    for command_name in ('pg_dump', 'pg_dump.exe'):
        resolved = shutil.which(command_name)
        if resolved:
            return resolved
    return None


def _build_location_label(settings_dict: dict) -> str:
    host = str(settings_dict.get('HOST') or 'localhost').strip()
    port = str(settings_dict.get('PORT') or '5432').strip()
    return f'{host}:{port}' if port else host


def _build_backup_filename(database_name: str) -> str:
    safe_name = re.sub(r'[^A-Za-z0-9_.-]+', '-', database_name or 'database')
    safe_name = safe_name.strip('-') or 'database'
    timestamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
    return f'{safe_name}-full-backup-{timestamp}.dump'


def get_database_backup_overview(alias: str = DEFAULT_DB_ALIAS) -> DatabaseBackupOverview:
    settings_dict = connections[alias].settings_dict
    database_name = str(settings_dict.get('NAME') or alias)
    if _is_postgresql_engine(settings_dict.get('ENGINE', '')):
        pg_dump_path = _resolve_pg_dump_path()
        if pg_dump_path:
            return DatabaseBackupOverview(
                engine_label='PostgreSQL',
                database_name=database_name,
                location_label=_build_location_label(settings_dict),
                format_label='Полный снимок PostgreSQL (.dump)',
                tool_label=Path(pg_dump_path).name,
                available=True,
            )
        return DatabaseBackupOverview(
            engine_label='PostgreSQL',
            database_name=database_name,
            location_label=_build_location_label(settings_dict),
            format_label='Полный снимок PostgreSQL (.dump)',
            tool_label='pg_dump',
            available=False,
            unavailable_reason=(
                'Утилита pg_dump не найдена. Добавьте её в PATH '
                'или задайте переменную окружения PG_DUMP_PATH.'
            ),
        )

    return DatabaseBackupOverview(
        engine_label=settings_dict.get('ENGINE', 'Неизвестная СУБД'),
        database_name=database_name,
        location_label=_build_location_label(settings_dict),
        format_label='Недоступно',
        tool_label='—',
        available=False,
        unavailable_reason='Полный резервный снимок сейчас поддерживается только для PostgreSQL.',
    )


def build_full_database_backup(alias: str = DEFAULT_DB_ALIAS) -> tuple[bytes, str]:
    overview = get_database_backup_overview(alias)
    if not overview.available:
        raise DatabaseBackupError(
            overview.unavailable_reason or 'Резервное копирование сейчас недоступно.',
        )

    settings_dict = connections[alias].settings_dict
    pg_dump_path = _resolve_pg_dump_path()
    if not pg_dump_path:
        raise DatabaseBackupError(
            'Не удалось определить путь к pg_dump для формирования резервной копии.',
        )

    command = [
        pg_dump_path,
        '--format=custom',
        '--encoding=UTF8',
        '--no-owner',
        '--no-privileges',
        '--create',
        '--dbname',
        str(settings_dict.get('NAME') or ''),
    ]

    if settings_dict.get('HOST'):
        command.extend(['--host', str(settings_dict['HOST'])])
    if settings_dict.get('PORT'):
        command.extend(['--port', str(settings_dict['PORT'])])
    if settings_dict.get('USER'):
        command.extend(['--username', str(settings_dict['USER'])])

    env = os.environ.copy()
    if settings_dict.get('PASSWORD'):
        env['PGPASSWORD'] = str(settings_dict['PASSWORD'])
    env.setdefault('PGCLIENTENCODING', 'UTF8')

    for option_name, env_name in OPTION_ENV_MAP.items():
        option_value = (settings_dict.get('OPTIONS') or {}).get(option_name)
        if option_value not in (None, ''):
            env[env_name] = str(option_value)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=env,
            timeout=600,
        )
    except OSError as exc:
        raise DatabaseBackupError(
            f'Не удалось запустить pg_dump: {exc}',
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise DatabaseBackupError(
            'Формирование резервной копии превысило допустимое время ожидания.',
        ) from exc

    if result.returncode != 0:
        error_details = result.stderr.decode('utf-8', errors='replace').strip()
        if not error_details:
            error_details = 'pg_dump завершился с ошибкой без пояснений.'
        raise DatabaseBackupError(
            f'Не удалось сформировать резервную копию БД: {error_details}',
        )

    backup_bytes = result.stdout
    if not backup_bytes:
        raise DatabaseBackupError(
            'pg_dump вернул пустой файл резервной копии.',
        )

    return backup_bytes, _build_backup_filename(overview.database_name)


def create_database_backup_record(
    *,
    backup_bytes: bytes,
    filename: str,
    created_by,
    alias: str = DEFAULT_DB_ALIAS,
) -> models.DatabaseBackup:
    overview = get_database_backup_overview(alias)
    record = models.DatabaseBackup(
        filename=filename,
        size_bytes=len(backup_bytes),
        database_name=overview.database_name,
        engine_label=overview.engine_label,
        tool_label=overview.tool_label,
        created_by=created_by if getattr(created_by, 'is_authenticated', False) else None,
    )
    try:
        record.file.save(filename, ContentFile(backup_bytes), save=False)
        record.save()
    except (OSError, DatabaseError) as exc:
        raise DatabaseBackupError(
            f'Резервная копия сформирована, но не сохранена в истории: {exc}',
        ) from exc
    return record
