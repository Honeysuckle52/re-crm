"""Dev-runserver с автоматическим запуском background worker."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.staticfiles.management.commands.runserver import (
    Command as DjangoRunserverCommand,
)
from django.core.management.commands.runserver import (
    Command as BaseRunserverCommand,
)

from ..background_worker import (
    DEFAULT_WORKER_LIMIT,
    DEFAULT_WORKER_SLEEP,
    build_worker_command,
)


class Command(DjangoRunserverCommand):
    help = (
        'Запускает Django runserver и автоматически поднимает '
        'process_background_jobs --loop в отдельном процессе.'
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--without-worker',
            action='store_true',
            help='Не запускать process_background_jobs вместе с dev-сервером.',
        )
        parser.add_argument(
            '--worker-limit',
            type=int,
            default=DEFAULT_WORKER_LIMIT,
            help='Сколько задач воркер обрабатывает за один проход.',
        )
        parser.add_argument(
            '--worker-sleep',
            type=float,
            default=DEFAULT_WORKER_SLEEP,
            help='Пауза между пустыми циклами background worker.',
        )

    def get_handler(self, *args, **options):
        handler = BaseRunserverCommand.get_handler(self, *args, **options)
        if not options.get('use_static_handler', True):
            return handler
        return StaticFilesHandler(handler)

    def inner_run(self, *args, **options):
        worker_process = None
        if self._should_start_worker(options):
            worker_process = self._start_background_worker(options)
        try:
            return super().inner_run(*args, **options)
        finally:
            self._stop_background_worker(worker_process)

    def _should_start_worker(self, options) -> bool:
        if options.get('without_worker'):
            return False
        if options.get('use_reloader', True):
            return os.environ.get('RUN_MAIN') == 'true'
        return True

    def _start_background_worker(self, options):
        manage_py = Path(settings.BASE_DIR) / 'manage.py'
        command = build_worker_command(
            python_executable=sys.executable,
            manage_py=manage_py,
            limit=options.get('worker_limit'),
            sleep_seconds=options.get('worker_sleep'),
        )
        env = os.environ.copy()
        env.setdefault('PYTHONIOENCODING', 'utf-8')
        process = subprocess.Popen(
            command,
            cwd=str(settings.BASE_DIR),
            env=env,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Background worker started (pid={process.pid}).',
            ),
        )
        return process

    def _stop_background_worker(self, process):
        if process is None:
            return
        if process.poll() is not None:
            return
        self.stdout.write(self.style.WARNING('Stopping background worker...'))
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
