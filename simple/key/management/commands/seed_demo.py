"""Наполняет БД демо-данными."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...models import (
    Address,
    City,
    ClientProfile,
    Deal,
    DealStatus,
    EmployeeProfile,
    House,
    OperationType,
    Property,
    PropertyFeature,
    PropertyFeatureValue,
    PropertyPhoto,
    PropertyStatus,
    Request,
    RequestStatus,
    Street,
    Task,
    TaskStatus,
    User,
    UserRole,
)


_IMAGE_COLORS = [
    (205, 227, 211),  # мятно-салатовый
    (233, 214, 185),  # светло-бежевый
    (197, 216, 232),  # бледно-голубой
    (232, 199, 199),  # розово-персиковый
    (214, 214, 227),  # сиренево-серый
]


class Command(BaseCommand):
    help = 'Заполняет БД демонстрационными пользователями, объектами, заявками и задачами.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Сначала удалить ранее созданные демо-данные.',
        )
        parser.add_argument(
            '--force-images', action='store_true',
            help='Перезаписать изображения media/2026/04/1..5.jpg.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('-> Проверяем справочники (seed_dictionaries)...')
        call_command('seed_dictionaries')

        if options['flush']:
            self._flush_demo()

        self._ensure_demo_images(force=options['force_images'])

        users = self._seed_users()
        self.stdout.write(self.style.SUCCESS(
            f'   Пользователи: {len(users)} (admin/manager/agents/clients).'
        ))

        addresses = self._seed_addresses()

        properties = self._seed_properties(addresses, users)
        self.stdout.write(self.style.SUCCESS(
            f'   Объекты недвижимости: {len(properties)}.'
        ))

        requests = self._seed_requests(users, properties)
        self.stdout.write(self.style.SUCCESS(
            f'   Заявки: {len(requests)}.'
        ))

        tasks = self._seed_tasks(users, properties, requests)
        self.stdout.write(self.style.SUCCESS(
            f'   Задачи: {len(tasks)}.'
        ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Демо-данные готовы. Логины/пароли:'
        ))
        for u in users.values():
            role = u.role.name if u.role_id else '—'
            self.stdout.write(
                f'    {u.username:<14}  ({u.user_type:<8}, роль: {role})   '
                f'пароль: demo12345'
            )

    def _flush_demo(self):
        """Удаляет демо-данные, оставляя справочники и реальных пользователей."""
        self.stdout.write(self.style.WARNING('-> Удаляем демо-данные...'))
        demo_usernames = [
            'demo_admin', 'demo_manager', 'demo_agent1', 'demo_agent2',
            'demo_client1', 'demo_client2', 'demo_client3',
        ]
        demo_users = User.objects.filter(username__in=demo_usernames)
        Task.objects.filter(created_by__in=demo_users).delete()
        Request.objects.filter(client__in=demo_users).delete()
        Deal.objects.filter(client__in=demo_users).delete()

        PropertyPhoto.objects.filter(
            image__startswith='2026/04/'
        ).delete()
        Property.objects.filter(
            title__startswith='[DEMO]'
        ).delete()

        demo_users.delete()
        City.objects.filter(name='Демо-город').delete()

    def _ensure_demo_images(self, force: bool):
        """Рендерит демо-картинки в ``MEDIA_ROOT/2026/04``."""
        from PIL import Image, ImageDraw, ImageFont

        media_root = Path(settings.MEDIA_ROOT)
        target_dir = media_root / '2026' / '04'
        target_dir.mkdir(parents=True, exist_ok=True)

        legacy_dir = media_root / 'properties' / '2026' / '04'
        if legacy_dir.exists():
            for item in legacy_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                except OSError:
                    self.stdout.write(self.style.WARNING(
                        f'  !! Не удалось удалить {item}'
                    ))
            self.stdout.write(self.style.WARNING(
                f'  -- Очищен устаревший каталог {legacy_dir}'
            ))

        try:
            font = ImageFont.truetype(
                'DejaVuSans-Bold.ttf', size=220,
            )
        except OSError:
            font = ImageFont.load_default()

        for idx in range(1, 6):
            path = target_dir / f'{idx}.jpg'
            if path.exists() and not force:
                continue
            color = _IMAGE_COLORS[idx - 1]
            img = Image.new('RGB', (1280, 800), color=color)
            draw = ImageDraw.Draw(img)
            text = str(idx)
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                tw, th = draw.textsize(text, font=font)
            draw.text(
                ((1280 - tw) / 2, (800 - th) / 2 - 40),
                text, fill=(40, 72, 70), font=font,
            )
            draw.text(
                (40, 720), f'Демо-объект #{idx}',
                fill=(40, 72, 70),
            )
            img.save(path, format='JPEG', quality=82)
            self.stdout.write(f'   сохранено {path.relative_to(media_root)}')

    def _seed_users(self) -> dict[str, User]:
        """Создаёт демо-пользователей с профилями."""
        role_admin = UserRole.objects.get(code='admin')
        role_manager = UserRole.objects.get(code='manager')
        role_agent = UserRole.objects.get(code='agent')

        PEOPLE = [
            ('demo_admin',   'admin@demo.re',   '+70000000001', 'employee', role_admin,
             'Арсений',  'Администратов', {'position': 'Главный администратор'}),
            ('demo_manager', 'manager@demo.re', '+70000000002', 'employee', role_manager,
             'Марина',   'Менеджерова',   {'position': 'Руководитель отдела'}),
            ('demo_agent1',  'agent1@demo.re', '+70000000003', 'employee', role_agent,
             'Алексей',  'Агентов',       {'position': 'Агент по продажам'}),
            ('demo_agent2',  'agent2@demo.re', '+70000000004', 'employee', role_agent,
             'Елена',    'Иванова',       {'position': 'Агент по аренде'}),
            ('demo_client1', 'c1@demo.re',     '+70000000005', 'client',   None,
             'Пётр',     'Клиентов',      {}),
            ('demo_client2', 'c2@demo.re',     '+70000000006', 'client',   None,
             'Ольга',    'Смирнова',      {}),
            ('demo_client3', 'c3@demo.re',     '+70000000007', 'client',   None,
             'Иван',     'Петров',        {}),
        ]

        users: dict[str, User] = {}
        for (username, email, phone, user_type, role,
             first_name, last_name, extra) in PEOPLE:
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    'email': email,
                    'phone': phone,
                    'user_type': user_type,
                    'role': role,
                    'is_staff': user_type == 'employee',
                    'is_active': True,
                    'is_email_verified': True,
                },
            )
            if created or not user.has_usable_password():
                user.set_password('demo12345')
                user.save(update_fields=['password'])

            if user_type == 'employee':
                EmployeeProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'position': extra.get('position', ''),
                        'department': 'Основной офис',
                        'hire_date': date(2024, 1, 15),
                    },
                )
            else:
                ClientProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'preferred_contact_method': 'phone',
                    },
                )

            users[username] = user
        return users

    def _seed_addresses(self) -> list[Address]:
        """Создаёт 5 адресов в «Демо-городе»."""
        city, _ = City.objects.get_or_create(
            name='Демо-город',
            defaults={'region': 'Демо-область'},
        )
        street, _ = Street.objects.get_or_create(
            city=city, name='Центральная',
            defaults={'street_type': 'ул.'},
        )
        addresses: list[Address] = []
        for i in range(1, 6):
            house, _ = House.objects.get_or_create(
                street=street,
                house_number=str(i),
                building=None,
                defaults={'postal_code': '100000'},
            )
            addr, _ = Address.objects.get_or_create(
                house=house,
                apartment_number=str(10 + i),
                defaults={'floor': i, 'entrance': 1},
            )
            addresses.append(addr)
        return addresses

    def _seed_properties(
        self,
        addresses: list[Address],
        users: dict[str, User],
    ) -> list[Property]:
        sale = OperationType.objects.get(code='sale')
        rent = OperationType.objects.get(code='rent')
        status_active = PropertyStatus.objects.get(code='active')
        status_reserved = PropertyStatus.objects.get(code='reserved')

        features = list(PropertyFeature.objects.all()[:8])

        specs = [
            ('[DEMO] Светлая студия у парка',
             sale, status_active, 5_400_000, 1, 32.5, 4, 9),
            ('[DEMO] 2-комн. квартира с ремонтом',
             sale, status_active, 8_900_000, 2, 54.0, 6, 16),
            ('[DEMO] 3-комн. семейная квартира',
             sale, status_reserved, 12_500_000, 3, 78.3, 10, 12),
            ('[DEMO] Уютная студия в аренду',
             rent, status_active, 35_000, 1, 29.0, 2, 9),
            ('[DEMO] 2-комн. для аренды, центр',
             rent, status_active, 58_000, 2, 48.5, 5, 10),
        ]

        created: list[Property] = []
        for idx, spec in enumerate(specs, start=1):
            (title, op, status, price, rooms, area,
             floor, total_floors) = spec
            prop, _ = Property.objects.update_or_create(
                title=title,
                defaults={
                    'operation_type': op,
                    'status': status,
                    'address': addresses[idx - 1],
                    'price': float(price),
                    'price_per_sqm': float(price) / float(area),
                    'area_total': area,
                    'rooms_count': rooms,
                    'floor_number': floor,
                    'total_floors': total_floors,
                    'description': (
                        f'Демонстрацион��ый объект №{idx}. '
                        'Создан командой seed_demo, используется '
                        'для проверки работы системы.'
                    ),
                },
            )

            PropertyFeatureValue.objects.filter(property=prop).delete()
            for feat in features[idx - 1: idx - 1 + 3]:
                PropertyFeatureValue.objects.create(
                    property=prop, feature=feat, value='да',
                )

            PropertyPhoto.objects.filter(property=prop).delete()
            PropertyPhoto.objects.create(
                property=prop,
                image=f'2026/04/{idx}.jpg',
                caption=f'Фото объекта №{idx}',
                is_cover=True,
                order=0,
            )
            created.append(prop)
        return created

    def _seed_requests(
        self,
        users: dict[str, User],
        properties: list[Property],
    ) -> list[Request]:
        sale = OperationType.objects.get(code='sale')
        rent = OperationType.objects.get(code='rent')
        st_open = RequestStatus.objects.get(code='open')
        st_processing = RequestStatus.objects.get(code='processing')
        st_completed = RequestStatus.objects.get(code='completed')

        client1 = users['demo_client1']
        client2 = users['demo_client2']
        client3 = users['demo_client3']
        agent1 = users['demo_agent1']
        agent2 = users['demo_agent2']

        SPECS = [
            (client1, None, st_open, sale, properties[0], 1,
             (4_000_000, 6_000_000),
             'Ищу однокомнатную квартиру или студию в пешей доступности от метро.'),
            (client2, agent1, st_processing, sale, properties[1], 2,
             (7_000_000, 10_000_000),
             'Нужна 2-комнатная квартира с современным ремонтом.'),
            (client3, agent1, st_processing, sale, properties[2], 3,
             (10_000_000, 14_000_000),
             'Ищем семейную квартиру с раздельными комнатами.'),
            (client1, agent2, st_completed, rent, properties[3], 1,
             (30_000, 40_000),
             'Студия в аренду на 6 месяцев.'),
            (client2, agent2, st_open, rent, None, 2,
             (50_000, 65_000),
             'Рассматриваем долгосрочную аренду 2-комнатной.'),
        ]

        requests: list[Request] = []
        for client, agent, status, op_type, prop, rooms, price_range, desc in SPECS:
            req, created = Request.objects.get_or_create(
                client=client, operation_type=op_type,
                description=desc,
                defaults={
                    'agent': agent,
                    'property': prop,
                    'status': status,
                    'rooms_count': rooms,
                    'min_price': price_range[0],
                    'max_price': price_range[1],
                },
            )
            req.agent = agent
            req.property = prop
            req.status = status
            req.rooms_count = rooms
            req.min_price = price_range[0]
            req.max_price = price_range[1]
            if status.code in Request.TERMINAL_STATUS_CODES:
                req.closed_at = timezone.now() - timedelta(days=2)
            req.save()
            requests.append(req)
        return requests

    def _seed_tasks(
        self,
        users: dict[str, User],
        properties: list[Property],
        requests: list[Request],
    ) -> list[Task]:
        """Создаёт демо-задачи."""
        st_new = TaskStatus.objects.get(code='new')
        st_in_progress = TaskStatus.objects.get(code='in_progress')
        st_done = TaskStatus.objects.get(code='done')

        try:
            manager = users['demo_manager']
            agent1 = users['demo_agent1']
            agent2 = users['demo_agent2']
            client1 = users['demo_client1']
            client2 = users['demo_client2']
            client3 = users['demo_client3']
        except KeyError as exc:
            self.stdout.write(self.style.WARNING(
                f'   !! Не найден демо-пользователь {exc}; задачи не создаются.'
            ))
            return []

        if len(properties) < 5:
            self.stdout.write(self.style.WARNING(
                f'   !! Ожидалось 5 объектов, получено {len(properties)}; '
                'часть задач может быть пропущена.'
            ))
        if len(requests) < 4:
            self.stdout.write(self.style.WARNING(
                f'   !! Ожидалось ≥4 заявок, получено {len(requests)}; '
                'часть задач может быть пропущена.'
            ))

        now = timezone.now()

        def _safe(seq, idx):
            return seq[idx] if 0 <= idx < len(seq) else None

        SPECS = [
            dict(
                title='[DEMO] Позвонить клиенту Пётр Клиентов',
                description='Уточнить требования по студии, предложить варианты.',
                task_type='call',
                priority='high', status=st_new, assignee=agent1,
                created_by=manager, client=client1,
                property=_safe(properties, 0),
                request=_safe(requests, 0),
                due_date=now + timedelta(hours=8),
            ),
            dict(
                title='[DEMO] Организовать показ 2-комн. квартиры',
                description='Согласовать время показа с клиенткой Ольгой.',
                task_type='showing',
                priority='normal', status=st_in_progress, assignee=agent1,
                created_by=manager, client=client2,
                property=_safe(properties, 1),
                request=_safe(requests, 1),
                due_date=now + timedelta(days=1),
            ),
            dict(
                title='[DEMO] Подготовить подборку 3-комн. квартир',
                description='Собрать 3–5 вариантов для клиента Ивана Петрова.',
                task_type='property_search',
                priority='normal', status=st_in_progress, assignee=agent1,
                created_by=manager, client=client3,
                property=_safe(properties, 2),
                request=_safe(requests, 2),
                due_date=now + timedelta(days=2),
            ),
            dict(
                title='[DEMO] Оформить договор аренды студии',
                description='Проверить пакет документов и отправить на подпись.',
                task_type='documents',
                priority='high', status=st_done, assignee=agent2,
                created_by=manager, client=client1,
                property=_safe(properties, 3),
                request=_safe(requests, 3),
                due_date=now - timedelta(days=1),
            ),
            dict(
                title='[DEMO] Обновить описание объекта на сайте',
                description='Добавить фото, уточнить метраж, пересчитать цену за м².',
                task_type='other',
                priority='low', status=st_new, assignee=agent2,
                created_by=manager, client=None,
                property=_safe(properties, 4),
                request=None,
                due_date=now + timedelta(days=3),
            ),
        ]

        tasks: list[Task] = []
        for spec in SPECS:
            if not spec.get('assignee') or not spec.get('created_by'):
                self.stdout.write(self.style.WARNING(
                    f'   !! Пропуск задачи "{spec["title"]}": '
                    'нет assignee/created_by.'
                ))
                continue

            defaults = {k: v for k, v in spec.items()
                        if k not in ('title', 'assignee')}
            task, created = Task.objects.get_or_create(
                title=spec['title'],
                assignee=spec['assignee'],
                defaults=defaults,
            )
            if not created:
                for field, value in defaults.items():
                    setattr(task, field, value)
                task.save()

            if spec['status'].code == 'done' and task.completed_at is None:
                task.completed_at = now - timedelta(hours=6)
                task.save(update_fields=['completed_at'])
            tasks.append(task)
        return tasks
