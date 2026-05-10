"""Unified-команда заполнения справочников, demo- и GAR-данных."""
from __future__ import annotations

from collections.abc import Callable

from django.core.management.base import BaseCommand

from ...seeding import SeedDataService


class Command(BaseCommand):
    help = (
        'Единая команда заполнения проекта: '
        'справочники, demo-данные и выборка из GAR.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--only',
            choices=('all', 'dictionaries', 'demo', 'gar'),
            default='all',
            help='Какой этап выполнять: all, dictionaries, demo или gar.',
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
        parser.add_argument(
            '--with-gar',
            action='store_true',
            help='При --only all дополнительно добавить выборку адресов из GAR.',
        )
        parser.add_argument(
            '--gar-region',
            default='',
            help='Код региона GAR или список кодов через запятую. Если не указан, команда сама выберет до 5 доступных регионов.',
        )
        parser.add_argument(
            '--gar-limit',
            type=int,
            default=20,
            help='Сколько объектов создать на основе GAR.',
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
        with_gar = bool(options['with_gar'])
        gar_region = str(options['gar_region'] or '').strip()
        gar_limit = max(int(options['gar_limit'] or 0), 1)

        def seed_all() -> None:
            service.seed_dictionaries(flush=False)
            if flush:
                service.flush_demo()
                service.flush_gar()
            service.seed_demo(
                flush=False,
                force_images=force_images,
                ensure_dictionaries=False,
            )
            if with_gar:
                service.seed_gar(
                    region_code=gar_region,
                    limit=gar_limit,
                    flush=False,
                    ensure_dictionaries=False,
                )

        actions: dict[str, Callable[[], None]] = {
            'all': seed_all,
            'dictionaries': lambda: service.seed_dictionaries(flush=flush),
            'demo': lambda: service.seed_demo(
                flush=flush,
                force_images=force_images,
            ),
            'gar': lambda: service.seed_gar(
                region_code=gar_region,
                limit=gar_limit,
                flush=flush,
            ),
        }
        return actions[only]
