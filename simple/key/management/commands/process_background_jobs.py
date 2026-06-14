"""Обработка фоновых очередей приложения key."""
from __future__ import annotations

import signal
import time

from django.db import InterfaceError, OperationalError, close_old_connections
from django.core.management.base import BaseCommand

from ... import deals_service, mailing
from ..background_worker import (
    DEFAULT_WORKER_LIMIT,
    DEFAULT_WORKER_SLEEP,
    normalize_worker_limit,
    normalize_worker_sleep,
)


class Command(BaseCommand):
    help = 'Обрабатывает очереди писем и генерации договоров.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown_requested = False

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=DEFAULT_WORKER_LIMIT,
            help='Сколько писем и договоров забирать за один цикл.',
        )
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Крутить воркер в цикле, а не выполнять один проход.',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=DEFAULT_WORKER_SLEEP,
            help='Пауза между циклами в режиме --loop, если очередь пуста.',
        )

    def _request_shutdown(self, signum, frame):  # noqa: ARG002
        """Помечаем, что нужно завершиться, и прерываем сон."""
        if not self._shutdown_requested:
            self._shutdown_requested = True
            self.stdout.write(
                self.style.WARNING(
                    '\nПолучен сигнал остановки, завершаем текущий цикл...'
                ),
            )

    def _interruptible_sleep(self, seconds: float) -> None:
        """Сон, который можно прервать запросом на остановку."""
        if seconds <= 0:
            return
        # Спим маленькими шагами, чтобы быстро реагировать на Ctrl+C.
        step = 0.5
        remaining = seconds
        while remaining > 0 and not self._shutdown_requested:
            time.sleep(min(step, remaining))
            remaining -= step

    def handle(self, *args, **options):
        limit = normalize_worker_limit(options['limit'])
        loop = bool(options['loop'])
        sleep_seconds = normalize_worker_sleep(options['sleep'])

        # Перехватываем SIGINT (Ctrl+C) и SIGTERM, чтобы выйти без traceback.
        previous_sigint = signal.signal(signal.SIGINT, self._request_shutdown)
        try:
            previous_sigterm = signal.signal(signal.SIGTERM, self._request_shutdown)
        except (AttributeError, ValueError):
            # SIGTERM может отсутствовать на Windows или вне главного потока.
            previous_sigterm = None

        if loop:
            self.stdout.write(
                self.style.HTTP_INFO(
                    f'Воркер запущен в режиме --loop '
                    f'(limit={limit}, sleep={sleep_seconds}s). '
                    f'Нажмите Ctrl+C для остановки.'
                ),
            )

        cycles = 0
        totals = {
            'emails_sent': 0,
            'emails_failed': 0,
            'contracts_generated': 0,
            'contracts_failed': 0,
        }

        try:
            while not self._shutdown_requested:
                try:
                    email_summary = mailing.process_email_queue(limit=limit)
                    contract_summary = deals_service.process_contract_queue(limit=limit)
                except (OperationalError, InterfaceError) as exc:
                    close_old_connections()
                    self.stdout.write(
                        self.style.WARNING(
                            f'Потеря соединения с БД: {exc}. '
                            'Переподключаемся и продолжаем.'
                        ),
                    )
                    if not loop:
                        raise
                    self._interruptible_sleep(sleep_seconds)
                    continue
                processed_total = (
                    email_summary['processed']
                    + contract_summary['processed']
                )

                cycles += 1
                totals['emails_sent'] += email_summary['sent']
                totals['emails_failed'] += email_summary['failed']
                totals['contracts_generated'] += contract_summary['generated']
                totals['contracts_failed'] += contract_summary['failed']

                self.stdout.write(
                    self.style.SUCCESS(
                        'emails: '
                        f"processed={email_summary['processed']} "
                        f"sent={email_summary['sent']} "
                        f"failed={email_summary['failed']} | "
                        'contracts: '
                        f"processed={contract_summary['processed']} "
                        f"generated={contract_summary['generated']} "
                        f"failed={contract_summary['failed']}"
                    ),
                )

                if not loop:
                    break
                if processed_total == 0:
                    self._interruptible_sleep(sleep_seconds)
        finally:
            # Восстанавливаем прежние обработчики сигналов.
            signal.signal(signal.SIGINT, previous_sigint)
            if previous_sigterm is not None:
                try:
                    signal.signal(signal.SIGTERM, previous_sigterm)
                except (AttributeError, ValueError):
                    pass

            if loop:
                self.stdout.write('')
                self.stdout.write(
                    self.style.HTTP_INFO(
                        f'Итог за сессию: циклов={cycles} | '
                        f"emails sent={totals['emails_sent']} "
                        f"failed={totals['emails_failed']} | "
                        f"contracts generated={totals['contracts_generated']} "
                        f"failed={totals['contracts_failed']}"
                    ),
                )
                self.stdout.write(
                    self.style.SUCCESS('Воркер остановлен корректно.'),
                )
