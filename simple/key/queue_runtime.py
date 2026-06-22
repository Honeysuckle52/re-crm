# -*- coding: utf-8 -*-
"""Ленивый in-process запуск обработки очередей без постоянного воркера."""
from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.db import close_old_connections

from .management.background_worker import normalize_worker_limit

log = logging.getLogger(__name__)

_runner_lock = threading.Lock()
_runner_thread: threading.Thread | None = None
_rerun_requested = False


def is_enabled() -> bool:
    return bool(getattr(settings, 'BACKGROUND_AUTORUN_ENABLED', False))


def trigger_background_processing(*, reason: str = '') -> bool:
    """Будит обработчик очередей, если он ещё не запущен."""
    if not is_enabled():
        return False

    global _runner_thread, _rerun_requested
    with _runner_lock:
        if _runner_thread is not None and _runner_thread.is_alive():
            _rerun_requested = True
            return False

        _rerun_requested = False
        _runner_thread = threading.Thread(
            target=_run_background_processing,
            name='key-queue-runtime',
            daemon=True,
        )
        _runner_thread.start()

    if reason:
        log.info('Lazy queue runner started: %s', reason)
    return True


def _run_background_processing() -> None:
    from . import deals_service, mailing

    global _runner_thread, _rerun_requested

    limit = normalize_worker_limit(
        getattr(settings, 'BACKGROUND_AUTORUN_LIMIT', 10),
    )
    max_passes = max(
        int(getattr(settings, 'BACKGROUND_AUTORUN_MAX_PASSES', 3) or 0),
        1,
    )
    should_restart = False

    try:
        for _ in range(max_passes):
            close_old_connections()

            email_summary = mailing.process_email_queue(limit=limit)
            contract_summary = deals_service.process_contract_queue(limit=limit)
            processed_total = (
                email_summary['processed']
                + contract_summary['processed']
            )

            with _runner_lock:
                rerun_requested = _rerun_requested
                _rerun_requested = False

            if processed_total == 0 and not rerun_requested:
                return
    except Exception:  # noqa: BLE001
        log.exception('Lazy queue runner failed.')
    finally:
        close_old_connections()
        with _runner_lock:
            if _rerun_requested:
                should_restart = True
                _rerun_requested = False
            _runner_thread = None

    if should_restart:
        trigger_background_processing(reason='rerun')
