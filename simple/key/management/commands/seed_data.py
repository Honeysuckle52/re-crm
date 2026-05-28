"""Unified-команда заполнения справочников и demo-данных."""
from __future__ import annotations

from collections.abc import Callable

from django.core.management.base import BaseCommand

from ...seeding import SeedDataService


class Command(BaseCommand):
    help = (
        'Единая команда заполнения проекта: '
        'справочники и demo-данные.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--only',
            choices=('all', 'dictionaries', 'demo'),
            default='all',
            help='Какой этап выполнять: all, dictionaries или demo.',
        )
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Очистить данные выбранного этапа перед заполнением.',
        )
        parser.add_argument(
            '--force-images',
            action='store_true',
            help='Перезаписать изображения demo-объектов.',
        )
    def handle(self, *args, **options):
        service = SeedDataService(self)
        execution = self._build_execution_plan(service, options)
        execution()

    def _build_execution_plan(
        self,
        service: SeedDataService,
        options,
    ) -> Callable[[], None]:
        only = options['only']
        flush = bool(options['flush'])
        force_images = bool(options['force_images'])

        def seed_all() -> None:
            service.seed_dictionaries(flush=False)
            if flush:
                service.flush_demo()
            service.seed_demo(
                flush=False,
                force_images=force_images,
                ensure_dictionaries=False,
            )

        actions: dict[str, Callable[[], None]] = {
            'all': seed_all,
            'dictionaries': lambda: service.seed_dictionaries(flush=flush),
            'demo': lambda: service.seed_demo(
                flush=flush,
                force_images=force_images,
            ),
        }
        return actions[only]
