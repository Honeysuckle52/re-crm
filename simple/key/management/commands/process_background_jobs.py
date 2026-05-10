"""Обработка фоновых очередей приложения key."""
from __future__ import annotations

import time

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

    def handle(self, *args, **options):
        limit = normalize_worker_limit(options['limit'])
        loop = bool(options['loop'])
        sleep_seconds = normalize_worker_sleep(options['sleep'])

        while True:
            email_summary = mailing.process_email_queue(limit=limit)
            contract_summary = deals_service.process_contract_queue(limit=limit)
            processed_total = (
                email_summary['processed']
                + contract_summary['processed']
            )
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
                time.sleep(sleep_seconds)
