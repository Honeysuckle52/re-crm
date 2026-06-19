# -*- coding: utf-8 -*-
"""Create a deterministic pool of users for authorization load testing."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import ClientProfile, User


DEFAULT_COUNT = 120
DEFAULT_PASSWORD = 'LoadTestAuth123!'
DEFAULT_PREFIX = 'loadtest.user'
DEFAULT_PHONE_PREFIX = '+7903'


class Command(BaseCommand):
    help = (
        'Создаёт пул тестовых пользователей для нагрузочного теста авторизации. '
        'Пользователи создаются как клиенты с предсказуемыми email и единым паролем.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=DEFAULT_COUNT,
            help=f'Сколько пользователей создать. По умолчанию: {DEFAULT_COUNT}.',
        )
        parser.add_argument(
            '--password',
            default=DEFAULT_PASSWORD,
            help='Пароль для всех создаваемых пользователей.',
        )
        parser.add_argument(
            '--prefix',
            default=DEFAULT_PREFIX,
            help=f'Префикс username/email. По умолчанию: {DEFAULT_PREFIX}.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = max(1, int(options['count']))
        password = str(options['password'])
        prefix = str(options['prefix']).strip() or DEFAULT_PREFIX

        created = 0
        updated = 0

        for index in range(1, count + 1):
            username = f'{prefix}.{index:03d}'
            email = f'{prefix}.{index:03d}@example.com'
            phone = f'{DEFAULT_PHONE_PREFIX}{index:07d}'

            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(
                    username=username,
                    email=email,
                    phone=phone,
                    user_type='client',
                    is_staff=False,
                    is_superuser=False,
                    is_active=True,
                    is_email_verified=True,
                    is_phone_verified=True,
                )
                created += 1
            else:
                user.email = email
                user.phone = phone
                user.user_type = 'client'
                user.role = None
                user.is_staff = False
                user.is_superuser = False
                user.is_active = True
                user.is_email_verified = True
                user.is_phone_verified = True
                updated += 1

            user.set_password(password)
            user.full_clean()
            user.save()

            ClientProfile.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': 'Load',
                    'last_name': f'Test{index:03d}',
                    'middle_name': '',
                    'client_kind': ClientProfile.CLIENT_KIND_INDIVIDUAL,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f'Load-test users ready: created={created}, updated={updated}, total={count}.'
        ))
        self.stdout.write(
            f'Credentials pattern: {prefix}.001@example.com .. {prefix}.{count:03d}@example.com / {password}'
        )
