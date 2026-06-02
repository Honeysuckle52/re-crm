"""Общий слой заполнения справочников и тестовых данных."""
from __future__ import annotations

import logging
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .twogis import TwoGisClient, apply_property_enrichment
from .dadata import DadataClient
from .models import (
    Address,
    City,
    ClientProfile,
    Deal,
    EmployeeProfile,
    House,
    OperationType,
    Property,
    PropertyPhoto,
    PropertyStatus,
    Request,
    RequestStatus,
    Street,
    Task,
    TaskStatus,
    User,
    UserRole,
    DealStatus,
)


logger = logging.getLogger(__name__)


OPERATION_TYPES = [
    {'code': 'sale', 'name': 'Продажа'},
    {'code': 'rent', 'name': 'Аренда'},
]

PROPERTY_STATUSES = [
    {'code': 'pending', 'name': 'На модерации'},
    {'code': 'active', 'name': 'Активно'},
    {'code': 'reserved', 'name': 'Зарезервировано'},
    {'code': 'sold', 'name': 'Продано'},
    {'code': 'rented', 'name': 'Сдано'},
    {'code': 'archived', 'name': 'В архиве'},
]

REQUEST_STATUSES = [
    {'code': 'open', 'name': 'Открыта'},
    {'code': 'processing', 'name': 'В обработке'},
    {'code': 'completed', 'name': 'Завершена'},
    {'code': 'cancelled', 'name': 'Отменена'},
    {'code': 'rejected', 'name': 'Отклонена'},
    {'code': 'lost', 'name': 'Потеряна'},
]

DEAL_STATUSES = [
    {'code': 'new', 'name': 'Новая', 'order': 10},
    {'code': 'negotiation', 'name': 'Переговоры', 'order': 20},
    {'code': 'documents', 'name': 'Подготовка документов', 'order': 30},
    {'code': 'signed', 'name': 'Договор подписан', 'order': 40},
    {'code': 'completed', 'name': 'Завершена', 'order': 50},
    {'code': 'cancelled', 'name': 'Отменена', 'order': 90},
]

TASK_STATUSES = [
    {'code': 'new', 'name': 'Новая', 'order': 10},
    {'code': 'in_progress', 'name': 'В работе', 'order': 20},
    {'code': 'waiting', 'name': 'Ожидание', 'order': 30},
    {'code': 'done', 'name': 'Выполнена', 'order': 40},
    {'code': 'cancelled', 'name': 'Отменена', 'order': 90},
]

USER_ROLES = [
    {
        'code': 'admin',
        'name': 'Администратор',
        'description': 'Полный доступ ко всем функциям системы',
        'max_active_tasks': 2,
        'max_in_progress_tasks': 1,
        'max_active_requests': 2,
    },
    {
        'code': 'manager',
        'name': 'Менеджер',
        'description': 'Управление сотрудниками, объектами и сделками',
        'max_active_tasks': 2,
        'max_in_progress_tasks': 1,
        'max_active_requests': 2,
    },
    {
        'code': 'agent',
        'name': 'Агент',
        'description': 'Работа с клиентами, объектами и заявками',
        'max_active_tasks': 2,
        'max_in_progress_tasks': 1,
        'max_active_requests': 2,
    },
]

DEMO_IMAGE_COLORS = [
    (205, 227, 211),
    (233, 214, 185),
    (197, 216, 232),
    (232, 199, 199),
    (214, 214, 227),
]

DEMO_USERNAMES = [
    'demo_admin',
    'demo_manager',
    'demo_agent1',
    'demo_agent2',
    'demo_client1',
    'demo_client2',
    'demo_client3',
]


class SeedLogger:
    def __init__(self, command=None):
        self.command = command

    def info(self, message: str):
        if self.command is not None:
            self.command.stdout.write(message)

    def success(self, message: str):
        if self.command is not None:
            self.command.stdout.write(self.command.style.SUCCESS(message))

    def warning(self, message: str):
        if self.command is not None:
            self.command.stdout.write(self.command.style.WARNING(message))


class SeedDataService:
    """Сервис заполнения проекта справочниками и demo-данными с обогащением через 2GIS."""

    _BATCH_CITY_REGIONS = {
        'Иркутск': 'Иркутская область',
        'Москва': 'Москва',
        'Хабаровск': 'Хабаровский край',
        'Чита': 'Забайкальский край',
    }
    _BATCH_CITY_CENTERS = {
        'Иркутск': (Decimal('52.2864'), Decimal('104.2807')),
        'Москва': (Decimal('55.7558'), Decimal('37.6173')),
        'Хабаровск': (Decimal('48.4802'), Decimal('135.0719')),
        'Чита': (Decimal('52.0333'), Decimal('113.5500')),
    }
    _BATCH_CITY_STREETS = {
        'Иркутск': [
            'ул. Ленина',
            'ул. Карла Маркса',
            'ул. Байкальская',
            'мкр. Солнечный',
            'ул. Декабрьских Событий',
        ],
        'Москва': [
            'Тверская ул.',
            'ул. Арбат',
            'Кутузовский пр-т',
            'Ленинский пр-т',
            'ул. Профсоюзная',
        ],
        'Хабаровск': [
            'ул. Муравьёва-Амурского',
            'ул. Ленина',
            'ул. Тургенева',
            'ул. Карла Маркса',
            'Амурский бульвар',
        ],
        'Чита': [
            'ул. Ленина',
            'ул. Амурская',
            'ул. Бутина',
            'ул. Чкалова',
            'ул. Костюшко-Григоровича',
        ],
    }

    def __init__(self, command=None, *, properties_count: int = 30, requests_count: int = 10):
        self.log = SeedLogger(command)
        self.properties_count = max(0, int(properties_count or 0))
        self.requests_count = max(0, int(requests_count or 0))

    def seed_dictionaries(self, *, flush: bool = False) -> dict[str, tuple[int, int]]:
        if flush:
            self.log.warning('Очищаем справочники...')
            UserRole.objects.all().delete()
            TaskStatus.objects.all().delete()
            DealStatus.objects.all().delete()
            RequestStatus.objects.all().delete()
            PropertyStatus.objects.all().delete()
            OperationType.objects.all().delete()

        created_counts = {
            'Типы операций': self._seed_rows(OperationType, OPERATION_TYPES, key='code'),
            'Статусы объектов': self._seed_rows(PropertyStatus, PROPERTY_STATUSES, key='code'),
            'Статусы заявок': self._seed_rows(RequestStatus, REQUEST_STATUSES, key='code'),
            'Статусы сделок': self._seed_rows(DealStatus, DEAL_STATUSES, key='code'),
            'Статусы задач': self._seed_rows(TaskStatus, TASK_STATUSES, key='code'),
            'Роли пользователей': self._seed_rows(UserRole, USER_ROLES, key='code'),
        }
        self.log.success('Справочники успешно заполнены:')
        for title, (created, updated) in created_counts.items():
            self.log.info(f'  {title:>22}: создано {created}, обновлено {updated}')
        return created_counts

    @transaction.atomic
    def seed_demo(
        self,
        *,
        flush: bool = False,
        force_images: bool = False,
        ensure_dictionaries: bool = True,
    ) -> dict:
        if ensure_dictionaries:
            self.log.info('-> Проверяем справочники...')
            self.seed_dictionaries(flush=False)

        if flush:
            self.flush_demo()

        self._ensure_demo_images(force=force_images)

        users = self._seed_users()
        self.log.success(f'   Пользователи: {len(users)} (admin/manager/agents/clients).')

        addresses = self._seed_demo_addresses()
        properties = self._seed_demo_properties(addresses)
        self.log.success(f'   Объекты недвижимости: {len(properties)}.')

        requests = self._seed_demo_requests(users, properties)
        self.log.success(f'   Заявки: {len(requests)}.')

        tasks = self._seed_demo_tasks(users, properties, requests)
        self.log.success(f'   Задачи: {len(tasks)}.')

        self.log.info('')
        self.log.success('Демо-данные готовы. Логины/пароли:')
        for user in users.values():
            role = user.role.name if user.role_id else '—'
            self.log.info(
                f'    {user.username:<14}  ({user.user_type:<8}, роль: {role})   пароль: demo12345',
            )
        properties_batch = self._create_properties_batch(properties_count=self.properties_count)
        self.log.success(f'   Дополнительные объекты недвижимости: {len(properties_batch)}.')

        requests_batch = self._create_requests_batch(requests_count=self.requests_count)
        self.log.success(f'   Дополнительные заявки: {len(requests_batch)}.')
        return {
            'users': len(users),
            'addresses': len(addresses),
            'properties': len(properties),
            'requests': len(requests),
            'tasks': len(tasks),
            'properties_batch': len(properties_batch),
            'requests_batch': len(requests_batch),
        }

    @transaction.atomic
    def flush_demo(self) -> dict:
        self.log.warning('-> Удаляем демо-данные...')
        demo_users = User.objects.filter(username__in=DEMO_USERNAMES)
        task_count = Task.objects.filter(created_by__in=demo_users).count()
        request_count = Request.objects.filter(client__in=demo_users).count()
        deal_count = Deal.objects.filter(client__in=demo_users).count()
        property_count = Property.objects.filter(description__contains='__seed_demo__').count()

        Task.objects.filter(created_by__in=demo_users).delete()
        Request.objects.filter(client__in=demo_users).delete()
        Deal.objects.filter(client__in=demo_users).delete()
        PropertyPhoto.objects.filter(image__startswith='2026/04/').delete()
        Property.objects.filter(description__contains='__seed_demo__').delete()
        demo_users.delete()
        City.objects.filter(name='Демо-город').delete()
        return {
            'tasks': task_count,
            'requests': request_count,
            'deals': deal_count,
            'properties': property_count,
        }

    @staticmethod
    def _seed_rows(model, rows, *, key: str) -> tuple[int, int]:
        created = 0
        updated = 0
        for row in rows:
            lookup = {key: row[key]}
            defaults = {field: value for field, value in row.items() if field != key}
            _, was_created = model.objects.update_or_create(defaults=defaults, **lookup)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    def _ensure_demo_images(self, *, force: bool = False):
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
                    self.log.warning(f'  !! Не удалось удалить {item}')
            self.log.warning(f'  -- Очищен устаревший каталог {legacy_dir}')

        try:
            font = ImageFont.truetype('DejaVuSans-Bold.ttf', size=220)
        except OSError:
            font = ImageFont.load_default()

        for index in range(1, 6):
            path = target_dir / f'{index}.jpg'
            if path.exists() and not force:
                continue
            color = DEMO_IMAGE_COLORS[index - 1]
            image = Image.new('RGB', (1280, 800), color=color)
            draw = ImageDraw.Draw(image)
            text = str(index)
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except AttributeError:
                text_width, text_height = draw.textsize(text, font=font)
            draw.text(
                ((1280 - text_width) / 2, (800 - text_height) / 2 - 40),
                text,
                fill=(40, 72, 70),
                font=font,
            )
            draw.text(
                (40, 720),
                f'Демо-объект #{index}',
                fill=(40, 72, 70),
            )
            image.save(path, format='JPEG', quality=82)
            self.log.info(f'   сохранено {path.relative_to(media_root)}')

    def _seed_users(self) -> dict[str, User]:
        role_admin = UserRole.objects.get(code='admin')
        role_manager = UserRole.objects.get(code='manager')
        role_agent = UserRole.objects.get(code='agent')

        people = [
            ('demo_admin', 'admin@demo.re', '+70000000001', 'employee', role_admin,
             'Арсений', 'Администраторов', {'position': 'Главный администратор'}),
            ('demo_manager', 'manager@demo.re', '+70000000002', 'employee', role_manager,
             'Марина', 'Менеджерова', {'position': 'Руководитель отдела'}),
            ('demo_agent1', 'agent1@demo.re', '+70000000003', 'employee', role_agent,
             'Алексей', 'Агентов', {'position': 'Агент по продажам'}),
            ('demo_agent2', 'agent2@demo.re', '+70000000004', 'employee', role_agent,
             'Елена', 'Иванова', {'position': 'Агент по аренде'}),
            ('demo_client1', 'c1@demo.re', '+70000000005', 'client', None,
             'Пётр', 'Клиентов', {}),
            ('demo_client2', 'c2@demo.re', '+70000000006', 'client', None,
             'Ольга', 'Смирнова', {}),
            ('demo_client3', 'c3@demo.re', '+70000000007', 'client', None,
             'Иван', 'Петров', {}),
        ]

        users: dict[str, User] = {}
        for (
            username,
            email,
            phone,
            user_type,
            role,
            first_name,
            last_name,
            extra,
        ) in people:
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

    # ------------------------------------------------------------------
    # Иркутские адреса через DaData (5 шт.)
    # ------------------------------------------------------------------

    # 5 реальных адресов Иркутска для поиска через DaData
    _IRKUTSK_QUERIES = [
        'Иркутск, ул. Ленина, 1',
        'Иркутск, ул. Карла Маркса, 23',
        'Иркутск, ул. Байкальская, 12',
        'Иркутск, ул. Советская, 55',
        'Иркутск, ул. Лермонтова, 79',
    ]

    def _seed_demo_addresses(self) -> list[Address]:
        """Создаёт 5 иркутских адресов через DaData + fallback на синтетику."""
        dadata = DadataClient()
        addresses: list[Address] = []

        for raw_query in self._IRKUTSK_QUERIES:
            address = self._address_from_dadata(dadata, raw_query)
            if address:
                addresses.append(address)

        # Если DaData недоступна — создаём синтетические адреса как раньше
        if not addresses:
            self.log.warning('   DaData недоступна — создаём синтетические иркутские адреса.')
            addresses = self._seed_synthetic_addresses()

        # Если частично получили адреса — добиваем синтетикой до 5
        if len(addresses) < 5:
            synthetic = self._seed_synthetic_addresses()
            addresses += synthetic[:5 - len(addresses)]

        return addresses

    def _address_from_dadata(self, dadata: DadataClient, query: str) -> Address | None:
        """Запрашивает один адрес из DaData и создаёт запись Address в БД."""
        try:
            suggestions = dadata.suggest_address(query, count=1)
        except Exception as exc:  # noqa: BLE001
            logger.warning('DaData: не удалось получить адрес для %r: %s', query, exc)
            return None

        if not suggestions:
            return None

        s = suggestions[0]
        city_name = (s.get('city') or '').strip()
        # DaData возвращает «г Иркутск» — убираем префикс типа
        for prefix in ('г ', 'г. ', 'город '):
            if city_name.lower().startswith(prefix):
                city_name = city_name[len(prefix):]
                break
        if not city_name:
            city_name = 'Иркутск'

        city_external_id = s.get('city_external_id') or None
        region = (s.get('region') or 'Иркутская область').strip()
        if city_external_id:
            city = City.objects.filter(external_id=city_external_id).first()
            if city is None:
                city = City.objects.create(external_id=city_external_id, name=city_name, region=region)
            else:
                City.objects.filter(pk=city.pk).update(name=city_name, region=region)
                city.refresh_from_db()
        else:
            city = City.objects.filter(name=city_name).first()
            if city is None:
                city = City.objects.create(name=city_name, region=region)

        street_name = (s.get('street') or '').strip()
        street_type = (s.get('street_type') or 'ул.').strip()
        if not street_name:
            return None

        street_external_id = s.get('street_external_id') or None
        if street_external_id:
            street = Street.objects.filter(external_id=street_external_id).first()
            if street is None:
                street = Street.objects.create(
                    external_id=street_external_id, city=city, name=street_name, street_type=street_type,
                )
            else:
                Street.objects.filter(pk=street.pk).update(city=city, name=street_name, street_type=street_type)
                street.refresh_from_db()
        else:
            street = Street.objects.filter(city=city, name=street_name).first()
            if street is None:
                street = Street.objects.create(city=city, name=street_name, street_type=street_type)

        house_number = (s.get('house') or '1').strip()
        house_external_id = s.get('house_external_id') or None
        if house_external_id:
            house = House.objects.filter(external_id=house_external_id).first()
            if house is None:
                house = House.objects.create(
                    external_id=house_external_id,
                    street=street,
                    house_number=house_number,
                    building=None,
                    postal_code=s.get('postal_code') or None,
                )
            else:
                House.objects.filter(pk=house.pk).update(
                    street=street,
                    house_number=house_number,
                    postal_code=s.get('postal_code') or None,
                )
                house.refresh_from_db()
        else:
            house = House.objects.filter(street=street, house_number=house_number, building=None).first()
            if house is None:
                house = House.objects.create(
                    street=street,
                    house_number=house_number,
                    building=None,
                    postal_code=s.get('postal_code') or None,
                )

        flat = (s.get('flat') or '').strip() or None
        address = Address.objects.filter(house=house, apartment_number=flat).first()
        if address is None:
            address = Address.objects.create(house=house, apartment_number=flat, floor=None, entrance=None)
        return address

    def _seed_synthetic_addresses(self) -> list[Address]:
        """Синтетические иркутские адреса — fallback при отсутствии DaData."""
        city = City.objects.filter(name='Иркутск').first()
        if city is None:
            city = City.objects.create(name='Иркутск', region='Иркутская область')

        street = Street.objects.filter(city=city, name='Ленина').first()
        if street is None:
            street = Street.objects.create(city=city, name='Ленина', street_type='ул.')
        addresses: list[Address] = []
        for index in range(1, 6):
            house, _ = House.objects.get_or_create(
                street=street,
                house_number=str(index),
                building=None,
                defaults={'postal_code': '664000'},
            )
            address, _ = Address.objects.get_or_create(
                house=house,
                apartment_number=str(10 + index),
                defaults={'floor': index, 'entrance': 1},
            )
            addresses.append(address)
        return addresses

    def _seed_demo_properties(self, addresses: list[Address]) -> list[Property]:
        sale = OperationType.objects.get(code='sale')
        rent = OperationType.objects.get(code='rent')
        op_map = {'sale': sale, 'rent': rent}

        status_active = PropertyStatus.objects.get(code='active')
        status_reserved = PropertyStatus.objects.get(code='reserved')
        status_map = {'active': status_active, 'reserved': status_reserved}

        created: list[Property] = []

        specs = [
            ('Студия у набережной', 'sale', 'active', Decimal('5200000'), 1, Decimal('31.50'), 3, 9),
            ('2-комн. с ремонтом', 'sale', 'active', Decimal('8700000'), 2, Decimal('52.00'), 6, 16),
            ('3-комн. семейная', 'sale', 'reserved', Decimal('12300000'), 3, Decimal('76.50'), 10, 12),
            ('Студия в аренду', 'rent', 'active', Decimal('34000'), 1, Decimal('28.00'), 2, 9),
            ('2-комн. аренда, центр', 'rent', 'active', Decimal('56000'), 2, Decimal('47.50'), 5, 10),
            ('Евро-двушка', 'sale', 'active', Decimal('7900000'), 2, Decimal('45.20'), 4, 12),
            ('Трёшка для семьи', 'sale', 'active', Decimal('13400000'), 3, Decimal('82.30'), 7, 14),
            ('Аренда с мебелью', 'rent', 'active', Decimal('41000'), 2, Decimal('39.80'), 8, 9),
            ('Лофт рядом с центром', 'sale', 'reserved', Decimal('10600000'), 1, Decimal('36.10'), 5, 8),
            ('Панорамная квартира', 'sale', 'active', Decimal('16200000'), 4, Decimal('108.00'), 11, 16),
            ('Семейная аренда', 'rent', 'active', Decimal('62000'), 3, Decimal('71.00'), 3, 10),
            ('Студия для инвестиций', 'sale', 'active', Decimal('4850000'), 1, Decimal('26.40'), 9, 16),
            ('Квартира с видом во двор', 'sale', 'active', Decimal('9100000'), 2, Decimal('54.60'), 6, 12),
            ('Аренда у парка', 'rent', 'reserved', Decimal('48000'), 2, Decimal('51.00'), 4, 11),
            ('Большая трёшка', 'sale', 'active', Decimal('14800000'), 3, Decimal('91.20'), 12, 15),
            ('Студия-апарт', 'rent', 'active', Decimal('38000'), 1, Decimal('24.80'), 10, 18),
            ('Квартира с ремонтом', 'sale', 'active', Decimal('11300000'), 2, Decimal('63.70'), 8, 14),
            ('Аренда для офиса', 'rent', 'active', Decimal('67000'), 4, Decimal('112.50'), 2, 7),
            ('Светлая двушка', 'sale', 'reserved', Decimal('8950000'), 2, Decimal('49.90'), 5, 13),
            ('Пентхаус', 'sale', 'active', Decimal('24500000'), 5, Decimal('154.30'), 15, 16),
        ]

        self.log.info('   Создаём 20 demo-объектов...')
        for idx, (suffix, op_code, st_code, price, rooms, area, floor, total_floors) in enumerate(
            specs, start=1
        ):
            address = addresses[(idx - 1) % len(addresses)]
            city_name = address.house.street.city.name if (
                address.house and address.house.street and address.house.street.city
            ) else 'Иркутск'
            street = address.house.street
            title = f'{city_name} — {suffix}'

            query_address = (
                f'{city_name}, '
                f'{street.street_type or ""} '
                f'{street.name}, '
                f'{address.house.house_number}'
            ).strip()

            property_obj, _ = Property.objects.update_or_create(
                title=title,
                defaults={
                    'operation_type': op_map[op_code],
                    'status': status_map[st_code],
                    'address': address,
                    'price': float(price),
                    'price_per_sqm': round(float(price) / float(area), 2),
                    'area_total': area,
                    'rooms_count': rooms,
                    'floor_number': floor,
                    'total_floors': total_floors,
                    'premises_type': Property.PREMISES_APARTMENT,
                    'description': (
                        f'Объект в г. {city_name}. '
                        'Создан командой seed_data. __seed_demo__'
                    ),
                },
            )

            PropertyPhoto.objects.filter(property=property_obj).delete()
            enriched = self._enrich_property_from_twogis(
                property_obj,
                address_query=query_address,
                city=city_name,
            )
            if not enriched:
                PropertyPhoto.objects.create(
                    property=property_obj,
                    image=f'2026/04/{((idx - 1) % 5) + 1}.jpg',
                    caption=f'Фото объекта №{idx}',
                    is_cover=True,
                    order=0,
                )
            created.append(property_obj)
            self.log.info(f'   [{idx}/20] {title}')

        return created

    def _seed_demo_requests(
        self,
        users: dict[str, User],
        properties: list[Property],
    ) -> list[Request]:
        sale = OperationType.objects.get(code='sale')
        rent = OperationType.objects.get(code='rent')
        status_open = RequestStatus.objects.get(code='open')
        status_processing = RequestStatus.objects.get(code='processing')
        status_completed = RequestStatus.objects.get(code='completed')

        specs = [
            (
                users['demo_client1'], None, status_open, sale, properties[0], 1,
                (4_000_000, 6_000_000),
                'Ищу однокомнатную квартиру или студию в пешей доступности от метро.',
            ),
            (
                users['demo_client2'], users['demo_agent1'], status_processing, sale, properties[1], 2,
                (7_000_000, 10_000_000),
                'Нужна 2-комнатная квартира с современным ремонтом.',
            ),
            (
                users['demo_client3'], users['demo_agent1'], status_processing, sale, properties[2], 3,
                (10_000_000, 14_000_000),
                'Ищем семейную квартиру с раздельными комнатами.',
            ),
            (
                users['demo_client1'], users['demo_agent2'], status_completed, rent, properties[3], 1,
                (30_000, 40_000),
                'Студия в аренду на 6 месяцев.',
            ),
            (
                users['demo_client2'], users['demo_agent2'], status_open, rent, None, 2,
                (50_000, 65_000),
                'Рассматриваем долгосрочную аренду 2-комнатной квартиры.',
            ),
        ]

        requests: list[Request] = []
        for client, agent, status, operation_type, property_obj, rooms, price_range, description in specs:
            request_obj, _ = Request.objects.get_or_create(
                client=client,
                operation_type=operation_type,
                description=description,
                defaults={
                    'agent': agent,
                    'property': property_obj,
                    'status': status,
                    'rooms_count': rooms,
                    'min_price': price_range[0],
                    'max_price': price_range[1],
                },
            )
            request_obj.agent = agent
            request_obj.property = property_obj
            request_obj.status = status
            request_obj.rooms_count = rooms
            request_obj.min_price = price_range[0]
            request_obj.max_price = price_range[1]
            if status.code in Request.TERMINAL_STATUS_CODES:
                request_obj.closed_at = timezone.now() - timedelta(days=2)
            request_obj.save()
            requests.append(request_obj)
        return requests

    def _seed_demo_tasks(
        self,
        users: dict[str, User],
        properties: list[Property],
        requests: list[Request],
    ) -> list[Task]:
        status_new = TaskStatus.objects.get(code='new')
        status_in_progress = TaskStatus.objects.get(code='in_progress')
        status_done = TaskStatus.objects.get(code='done')
        now = timezone.now()

        def safe(items, index):
            return items[index] if 0 <= index < len(items) else None

        specs = [
            {
                'title': 'Позвонить клиенту Пётр Клиентов',
                'description': 'Уточнить требования по студии, предложить варианты.',
                'task_type': 'call',
                'priority': 'high',
                'status': status_new,
                'assignee': users['demo_agent1'],
                'created_by': users['demo_manager'],
                'client': users['demo_client1'],
                'property': safe(properties, 0),
                'request': safe(requests, 0),
                'due_date': now + timedelta(hours=8),
            },
            {
                'title': 'Организовать показ 2-комн. квартиры',
                'description': 'Согласовать время показа с клиенткой Ольгой.',
                'task_type': 'showing',
                'priority': 'normal',
                'status': status_in_progress,
                'assignee': users['demo_agent1'],
                'created_by': users['demo_manager'],
                'client': users['demo_client2'],
                'property': safe(properties, 1),
                'request': safe(requests, 1),
                'due_date': now + timedelta(days=1),
            },
            {
                'title': 'Подготовить подборку 3-комн. квартир',
                'description': 'Собрать 3-5 вариантов для клиента Ивана Петрова.',
                'task_type': 'property_search',
                'priority': 'normal',
                'status': status_in_progress,
                'assignee': users['demo_agent1'],
                'created_by': users['demo_manager'],
                'client': users['demo_client3'],
                'property': safe(properties, 2),
                'request': safe(requests, 2),
                'due_date': now + timedelta(days=2),
            },
            {
                'title': 'Оформить договор аренды студии',
                'description': 'Проверить пакет документов и отправить на подпись.',
                'task_type': 'documents',
                'priority': 'high',
                'status': status_done,
                'assignee': users['demo_agent2'],
                'created_by': users['demo_manager'],
                'client': users['demo_client1'],
                'property': safe(properties, 3),
                'request': safe(requests, 3),
                'due_date': now - timedelta(days=1),
            },
            {
                'title': 'Обновить описание объекта на сайте',
                'description': 'Добавить фото, уточнить метраж, пересчитать цену за м².',
                'task_type': 'other',
                'priority': 'low',
                'status': status_new,
                'assignee': users['demo_agent2'],
                'created_by': users['demo_manager'],
                'client': None,
                'property': safe(properties, 4),
                'request': None,
                'due_date': now + timedelta(days=3),
            },
        ]

        tasks: list[Task] = []
        for spec in specs:
            defaults = {
                key: value
                for key, value in spec.items()
                if key not in ('title', 'assignee')
            }
            task_obj, created = Task.objects.get_or_create(
                title=spec['title'],
                assignee=spec['assignee'],
                defaults=defaults,
            )
            if not created:
                for field, value in defaults.items():
                    setattr(task_obj, field, value)
                task_obj.save()

            if spec['status'].code == 'done' and task_obj.completed_at is None:
                task_obj.completed_at = now - timedelta(hours=6)
                task_obj.save(update_fields=['completed_at'])
            tasks.append(task_obj)
        return tasks

    def _create_properties_batch(self, properties_count=30) -> list[Property]:
        """Создаёт дополнительный равномерный набор объектов по четырём городам."""
        if properties_count <= 0:
            return []

        operation_types = [
            OperationType.objects.filter(pk=1).first() or OperationType.objects.get(code='sale'),
            OperationType.objects.filter(pk=2).first() or OperationType.objects.get(code='rent'),
        ]
        statuses = [
            PropertyStatus.objects.filter(pk=1).first() or PropertyStatus.objects.get(code='pending'),
            PropertyStatus.objects.filter(pk=2).first() or PropertyStatus.objects.get(code='active'),
        ]
        premises_types = [
            Property.PREMISES_APARTMENT,
            Property.PREMISES_HOUSE,
            Property.PREMISES_OFFICE,
            Property.PREMISES_WAREHOUSE,
        ]

        rng = random.Random(20260602)
        cities = list(self._BATCH_CITY_STREETS.keys())
        created: list[Property] = []

        self.log.info(f'   Создаём/обновляем {properties_count} объектов по 4 городам...')
        for index in range(properties_count):
            city_name = cities[index % len(cities)]
            street_names = self._BATCH_CITY_STREETS[city_name]
            street_name = street_names[(index // len(cities)) % len(street_names)]
            local_index = index // len(cities)
            house_number = str(1 + local_index * 3)

            city, _ = City.objects.get_or_create(
                name=city_name,
                defaults={'region': self._BATCH_CITY_REGIONS.get(city_name, '')},
            )
            if not city.region and self._BATCH_CITY_REGIONS.get(city_name):
                city.region = self._BATCH_CITY_REGIONS[city_name]
                city.save(update_fields=['region'])

            street, _ = Street.objects.get_or_create(
                city=city,
                name=street_name,
                defaults={'street_type': ''},
            )
            house, _ = House.objects.get_or_create(
                street=street,
                house_number=house_number,
                building=None,
                defaults={'postal_code': None},
            )
            address, _ = Address.objects.get_or_create(
                house=house,
                apartment_number=None,
                defaults={'floor': None, 'entrance': None},
            )

            operation_type = rng.choice(operation_types)
            status = rng.choice(statuses)
            rooms_count = rng.randint(1, 5)
            area_total = Decimal(str(rng.randint(30, 150))).quantize(Decimal('0.01'))
            if operation_type.pk == 1 or operation_type.code == 'sale':
                price = float(rng.randint(2_000_000, 50_000_000))
            else:
                price = float(rng.randint(30_000, 200_000))
            title = f'{city.name}, {street.name} {house.house_number}, {rooms_count}-комн., {area_total}м²'
            description = (
                f'Объект в г. {city.name}. '
                'Создан расширенным заполнением seed_data. __seed_batch__'
            )

            info = self._search_batch_twogis(city_name, f'{street.name} {house.house_number}')
            lat, lon = self._coordinates_from_twogis_or_city_center(info, city_name)
            twogis_description = (info or {}).get('description') or ''
            if twogis_description:
                description = f'{twogis_description}\n\n{description}'

            existing = Property.objects.filter(
                address__house__street__city=city,
                address=address,
            ).first()
            defaults = {
                'title': title,
                'operation_type': operation_type,
                'status': status,
                'address': address,
                'coordinates_lat': lat,
                'coordinates_lon': lon,
                'twogis_org_id': self._twogis_text((info or {}).get('org_id')),
                'twogis_name': self._twogis_text((info or {}).get('name')),
                'twogis_address_full': self._twogis_text((info or {}).get('address_full')),
                'twogis_rubric': self._twogis_text((info or {}).get('rubric_name')),
                'twogis_synced_at': timezone.now() if info else None,
                'premises_type': rng.choice(premises_types),
                'price': price,
                'price_per_sqm': round(price / float(area_total), 2),
                'area_total': area_total,
                'rooms_count': rooms_count,
                'floor_number': rng.randint(1, 20),
                'total_floors': rng.randint(5, 25),
                'description': description,
            }
            if defaults['floor_number'] > defaults['total_floors']:
                defaults['floor_number'] = defaults['total_floors']

            if existing is None:
                property_obj = Property.objects.create(**defaults)
            else:
                property_obj = existing
                for field, value in defaults.items():
                    setattr(property_obj, field, value)
                property_obj.save()

            self._create_batch_photos(property_obj, (info or {}).get('photos') or [])
            created.append(property_obj)
            self.log.info(f'   [{index + 1}/{properties_count}] {title}')

        return created

    def _create_requests_batch(self, requests_count=10) -> list[Request]:
        """Создаёт дополнительный набор заявок клиентов на batch-объекты."""
        if requests_count <= 0:
            return []

        clients = list(User.objects.filter(user_type='client').order_by('pk'))
        if not clients:
            self.log.warning('   Нет клиентов для создания дополнительных заявок.')
            return []

        properties = list(
            Property.objects.filter(description__contains='__seed_batch__')
            .select_related('operation_type', 'address__house__street__city')
            .order_by('pk')
        )
        if not properties:
            self.log.warning('   Нет batch-объектов для создания дополнительных заявок.')
            return []

        agents = list(User.objects.filter(user_type='employee').order_by('pk'))
        request_statuses = [
            RequestStatus.objects.get_or_create(code='pending', defaults={'name': 'Ожидает обработки'})[0],
            RequestStatus.objects.get_or_create(code='in_progress', defaults={'name': 'В работе'})[0],
        ]
        rng = random.Random(20260603)
        created: list[Request] = []

        self.log.info(f'   Создаём/обновляем {requests_count} дополнительных заявок...')
        for index in range(requests_count):
            property_obj = rng.choice(properties)
            client = clients[index % len(clients)]
            agent = rng.choice(agents) if agents else None
            property_price = Decimal(str(property_obj.price or 0))
            min_price = max(Decimal('0'), property_price * Decimal('0.85'))
            max_price = property_price * Decimal('1.15')
            description = f'Дополнительная заявка seed_data #{index + 1}. __seed_batch_request__'
            defaults = {
                'agent': agent,
                'property': property_obj,
                'operation_type': property_obj.operation_type,
                'status': rng.choice(request_statuses),
                'property_type': property_obj.premises_type,
                'min_price': float(min_price),
                'max_price': float(max_price),
                'min_area': property_obj.area_total,
                'max_area': property_obj.area_total,
                'rooms_count': property_obj.rooms_count,
                'address_preferences': str(property_obj.address),
            }
            request_obj, was_created = Request.objects.get_or_create(
                client=client,
                description=description,
                defaults=defaults,
            )
            if not was_created:
                for field, value in defaults.items():
                    setattr(request_obj, field, value)
                request_obj.save()
            created.append(request_obj)
            self.log.info(f'   [{index + 1}/{requests_count}] заявка для {client.username}')

        return created

    @staticmethod
    def _search_batch_twogis(city_name: str, address: str) -> dict | None:
        try:
            return TwoGisClient().search_by_address(f'{city_name} {address}')
        except Exception as exc:  # noqa: BLE001
            logger.warning('2GIS batch search failed for %s %s: %s', city_name, address, exc)
            return None

    def _coordinates_from_twogis_or_city_center(
        self,
        info: dict | None,
        city_name: str,
    ) -> tuple[Decimal, Decimal]:
        lat = (info or {}).get('lat')
        lon = (info or {}).get('lon')
        if lat is None or lon is None:
            return self._BATCH_CITY_CENTERS[city_name]
        return (
            Decimal(str(lat)).quantize(Decimal('0.00000001')),
            Decimal(str(lon)).quantize(Decimal('0.00000001')),
        )

    @staticmethod
    def _twogis_text(value) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, list):
            text = ', '.join(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value).strip()
        return text or None

    @staticmethod
    def _create_batch_photos(property_obj: Property, photo_urls: list[str]) -> None:
        if not photo_urls or PropertyPhoto.objects.filter(property=property_obj).exists():
            return
        for order, url in enumerate(photo_urls[:3]):
            PropertyPhoto.objects.create(
                property=property_obj,
                url=url,
                caption='2GIS',
                is_cover=(order == 0),
                order=order,
            )

    def _enrich_property_from_twogis(
        self,
        property_obj: 'Property',
        *,
        address_query: str,
        city: str = '',
    ) -> bool:
        """Проверяет адрес через 2GIS и при наличии данных обогащает объект."""
        try:
            client = TwoGisClient()
            if not client.api_key:
                return False

            info = client.search_by_address(address_query, city=city)
            if not info:
                return False

            created = apply_property_enrichment(property_obj, info)
            if created:
                self.log.info(
                    f'   2GIS: {created} photo cards added for "{property_obj.title}"',
                )
            return True

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                '2GIS enrichment for property pk=%s (%r) failed: %s',
                property_obj.pk, address_query, exc,
            )
            return False

    @staticmethod
    def _parse_region_codes(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
        items = value if isinstance(value, (list, tuple)) else [value]
        region_codes: list[str] = []
        seen: set[str] = set()
        for item in items:
            for code in str(item or '').split(','):
                normalized = code.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                region_codes.append(normalized)
        return region_codes
