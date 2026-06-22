# -*- coding: utf-8 -*-
"""Общие helper'ы для dev-запуска background worker."""
from __future__ import annotations

from pathlib import Path


DEFAULT_WORKER_LIMIT = 10
DEFAULT_WORKER_SLEEP = 2.0
DEFAULT_WORKER_MAX_SLEEP = 30.0


def normalize_worker_limit(value) -> int:
    return max(int(value or 0), 1)


def normalize_worker_sleep(value) -> float:
    return max(float(value or 0), 0.1)


def normalize_worker_max_sleep(value, *, base_sleep: float | None = None) -> float:
    minimum = normalize_worker_sleep(base_sleep) if base_sleep is not None else 0.1
    return max(float(value or 0), minimum)


def build_worker_command(
    *,
    python_executable: str,
    manage_py: Path,
    limit,
    sleep_seconds,
    max_sleep_seconds,
) -> list[str]:
    return [
        python_executable,
        str(manage_py),
        'process_background_jobs',
        '--loop',
        '--limit',
        str(normalize_worker_limit(limit)),
        '--sleep',
        str(normalize_worker_sleep(sleep_seconds)),
        '--max-sleep',
        str(normalize_worker_max_sleep(
            max_sleep_seconds,
            base_sleep=sleep_seconds,
        )),
    ]
