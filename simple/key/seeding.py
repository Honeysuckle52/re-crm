"""Общий слой заполнения справочников и тестовых данных."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .gar_seed import GarResolvedUnit, GarSampler
from .twogis import TwoGisClient
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
    DealStatus,
)


logger = logging.getLogger(__name__)


OPERATION_TYPES = [
    {'code': 'sale', 'name': 'Продажа'},
    {'code': 'rent', 'name': 'Аренда'},
]

PROPERTY_STATUSES = [
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

PROPERTY_FEATURES = [
    {'name': 'Балкон', 'category': 'Комфорт'},
    {'name': 'Лоджия', 'category': 'Комфорт'},
    {'name': 'Свежий ремонт', 'category': 'Состояние'},
    {'name': 'Требует ремонта', 'category': 'Состояние'},
    {'name': 'Парковка', 'category': 'Инфраструктура'},
    {'name': 'Лифт', 'category': 'Инфраструктура'},
    {'name': 'Мебель', 'category': 'Комфорт'},
    {'name': 'Бытовая техника', 'category': 'Комфорт'},
    {'name': 'Интернет', 'category': 'Коммуникации'},
    {'name': 'Кондиционер', 'category': 'Комфорт'},
    {'name': 'Охрана', 'category': 'Безопасность'},
    {'name': 'Видеонаблюдение', 'category': 'Безопасность'},
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
    """Сервис заполнения проекта справочниками, демо-данными и GAR-данными."""

    def __init__(self, command=None):
        self.log = SeedLogger(command)

    def seed_dictionaries(self, *, flush: bool = False) -> dict[str, tuple[int, int]]:
        if flush:
            self.log.warning('Очищаем справочники...')
            PropertyFeature.objects.all().delete()
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
            'Характеристики': self._seed_rows(PropertyFeature, PROPERTY_FEATURES, key='name'),
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
        return {
            'users': len(users),
            'addresses': len(addresses),
            'properties': len(properties),
            'requests': len(requests),
            'tasks': len(tasks),
        }

    @transaction.atomic
    def seed_gar(
        self,
        *,
        region_code: str | None = None,
        limit: int = 20,
        flush: bool = False,
        ensure_dictionaries: bool = True,
    ) -> dict:
        if ensure_dictionaries:
            self.log.info('-> Проверяем справочники...')
            self.seed_dictionaries(flush=False)
        if flush:
            self.flush_gar()

        sampler = GarSampler()
        requested_regions = self._parse_region_codes(region_code)
        if requested_regions:
            region_codes = requested_regions
            if len(region_codes) == 1:
                region_codes = sampler.suggest_region_codes(
                    preferred=region_codes,
                    limit=5,
                )
        else:
            region_codes = sampler.suggest_region_codes(limit=5)
        if not region_codes:
            self.log.warning('GAR-каталоги не найдены. Проверьте GAR_ROOT и наличие регионов в выгрузке.')
            return {
                'properties': 0,
                'created': 0,
                'updated': 0,
                'region_codes': [],
            }
        self.log.info('-> GAR: регионы ' + ', '.join(region_codes))
        units = sampler.sample(region_codes=region_codes, limit=limit)
        if not units:
            self.log.warning('GAR-данные не найдены или не дали подходящих адресов.')
            return {
                'properties': 0,
                'created': 0,
                'updated': 0,
                'region_codes': region_codes,
            }

        sale = OperationType.objects.get(code='sale')
        rent = OperationType.objects.get(code='rent')
        status_active = PropertyStatus.objects.get(code='active')
        status_reserved = PropertyStatus.objects.get(code='reserved')
        features = list(PropertyFeature.objects.order_by('name')[:8])

        created_count = 0
        updated_count = 0
        total = 0

        for index, unit in enumerate(units, start=1):
            city, _ = City.objects.update_or_create(
                external_id=unit.city_guid,
                defaults={
                    'name': unit.city_name,
                    'region': unit.region_name,
                },
            )
            street, _ = Street.objects.update_or_create(
                external_id=unit.street_guid,
                defaults={
                    'city': city,
                    'name': unit.street_name,
                    'street_type': unit.street_type,
                },
            )
            house, _ = House.objects.update_or_create(
                external_id=unit.house_guid,
                defaults={
                    'street': street,
                    'house_number': unit.house_number,
                    'building': None,
                    'structure': None,
                    'postal_code': None,
                },
            )
            address, _ = Address.objects.get_or_create(
                house=house,
                apartment_number=unit.apartment_number or None,
                defaults={
                    'entrance': None,
                    'floor': None,
                },
            )

            rooms = 1 + ((index - 1) % 3)
            area_total = Decimal('28.00') + Decimal((index - 1) * 7)
            operation_type = sale if index % 3 else rent
            status = status_reserved if index % 5 == 0 else status_active
            price = self._gar_price(index=index, rooms=rooms, operation_code=operation_type.code)
            street_label = f'{street.street_type or ""} {street.name}'.strip()
            apartment_suffix = f', кв. {unit.apartment_number}' if unit.apartment_number else ''
            title = (
                f'[GAR] {rooms}-комн. объект, {city.name}, {street_label}, '
                f'д. {house.house_number}{apartment_suffix}'
            )
            defaults = {
                'operation_type': operation_type,
                'status': status,
                'address': address,
                'price': price,
                'price_per_sqm': round(price / float(area_total), 2),
                'area_total': area_total,
                'rooms_count': rooms,
                'floor_number': None,
                'total_floors': None,
                'description': (
                    'Тестовый объект, автоматически созданный на основе локальной '
                    f'выгрузки GAR/FIAS по региону {unit.region_name}.'
                ),
            }
            property_obj, was_created = Property.objects.update_or_create(
                title=title,
                defaults=defaults,
            )
            PropertyFeatureValue.objects.filter(property=property_obj).delete()
            for feature in features[(index - 1) % max(len(features), 1):]:
                if feature not in features:
                    continue
                PropertyFeatureValue.objects.create(
                    property=property_obj,
                    feature=feature,
                    value='да',
                )
                if PropertyFeatureValue.objects.filter(property=property_obj).count() >= 3:
                    break

            # Обогащаем объект данными из 2GIS (описание + фото по адресу).
            street_label = f'{street.street_type or ""} {street.name}'.strip()
            gar_address_query = (
                f'{city.name}, {street_label}, д. {house.house_number}'
            )
            self._enrich_property_from_twogis(
                property_obj,
                address_query=gar_address_query,
                city=city.name,
            )

            total += 1
            if was_created:
                created_count += 1
            else:
                updated_count += 1

        self.log.success(
            f'   GAR-объекты: {total} (создано: {created_count}, обновлено: {updated_count}).',
        )
        return {
            'properties': total,
            'created': created_count,
            'updated': updated_count,
            'region_codes': region_codes,
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

    @transaction.atomic
    def flush_gar(self) -> dict:
        self.log.warning('-> Уда��яем GAR-данные...')
        property_qs = Property.objects.filter(title__startswith='[GAR]')
        property_count = property_qs.count()
        property_qs.delete()

        address_qs = Address.objects.filter(
            properties__isnull=True,
            house__external_id__isnull=False,
        ).distinct()
        address_count = address_qs.count()
        address_qs.delete()

        house_qs = House.objects.filter(
            addresses__isnull=True,
            external_id__isnull=False,
        ).distinct()
        house_count = house_qs.count()
        house_qs.delete()

        street_qs = Street.objects.filter(
            houses__isnull=True,
            external_id__isnull=False,
        ).distinct()
        street_count = street_qs.count()
        street_qs.delete()

        city_qs = City.objects.filter(
            streets__isnull=True,
            external_id__isnull=False,
        ).distinct()
        city_count = city_qs.count()
        city_qs.delete()
        return {
            'properties': property_count,
            'addresses': address_count,
            'houses': house_count,
            'streets': street_count,
            'cities': city_count,
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
        """Создаёт 5 иркутских адресов че����ез DaData + fallback на синтетику."""
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

    # ------------------------------------------------------------------
    # GAR-адреса для дополнительных 15 объектов из 3 регионов
    # ------------------------------------------------------------------

    _GAR_EXTRA_REGIONS = ['01', '77', '38']  # Адыгея, Москва, Иркутская обл. (GAR в проекте)
    _GAR_EXTRA_PER_REGION = 5                # 5 объектов × 3 региона = 15

    # Адреса-заглушки для GAR-fallback — по одному городу на регион
    _GAR_FALLBACK_QUERIES = [
        # (регион, город, 5 запросов к DaData)
        ('01', 'Майкоп', [
            'Майкоп, ул. Ленина, 1',
            'Майкоп, ул. Пролетарская, 5',
            'Майкоп, ул. Краснооктябрьская, 15',
            'Майкоп, пр. Победы, 22',
            'Майкоп, ул. Советская, 44',
        ]),
        ('77', 'Москва', [
            'Москва, ул. Тверская, 10',
            'Москва, ул. Арбат, 7',
            'Москва, пр. Мира, 30',
            'Москва, ул. Новый Арбат, 20',
            'Москва, Кутузовский пр., 18',
        ]),
        ('38', 'Иркутск', [
            'Иркутск, ул. Декабрьских Событий, 6',
            'Иркутск, ул. Фурье, 11',
            'Иркутск, б-р Гагарина, 3',
            'Иркутск, ул. Дзержинского, 23',
            'Иркутск, ул. Горького, 41',
        ]),
    ]

    def _seed_gar_extra_addresses(self) -> list[tuple[Address, GarResolvedUnit]]:
        """Сэмплирует по 5 адресов из каждого из трёх GAR-регионов.

        Если папка GAR недоступна на текущей машине — создаёт адреса через
        DaData по реальным городам тех же регионов (01/77/38).
        """
        sampler = GarSampler()
        available = sampler.available_region_codes()

        gar_missing = [c for c in self._GAR_EXTRA_REGIONS if c not in available]
        if gar_missing:
            self.log.warning(
                f'   GAR не найден по пути {sampler.root} '
                f'(регионы {", ".join(gar_missing)} отсутствуют). '
                'Используем DaData-fallback для GAR-объектов.'
            )
            return self._seed_gar_fallback_via_dadata()

        result: list[tuple[Address, GarResolvedUnit]] = []
        for region_code in self._GAR_EXTRA_REGIONS:
            try:
                units = sampler.sample(region_codes=[region_code], limit=self._GAR_EXTRA_PER_REGION)
            except FileNotFoundError as exc:
                self.log.warning(f'   GAR-регион {region_code}: {exc}')
                continue

            for unit in units:
                city, _ = City.objects.update_or_create(
                    external_id=unit.city_guid,
                    defaults={
                        'name': unit.city_name,
                        'region': unit.region_name,
                    },
                )
                street, _ = Street.objects.update_or_create(
                    external_id=unit.street_guid,
                    defaults={
                        'city': city,
                        'name': unit.street_name,
                        'street_type': unit.street_type,
                    },
                )
                house, _ = House.objects.update_or_create(
                    external_id=unit.house_guid,
                    defaults={
                        'street': street,
                        'house_number': unit.house_number,
                        'building': None,
                        'postal_code': None,
                    },
                )
                address, _ = Address.objects.get_or_create(
                    house=house,
                    apartment_number=unit.apartment_number or None,
                    defaults={'floor': None, 'entrance': None},
                )
                result.append((address, unit))

        return result

    def _seed_gar_fallback_via_dadata(self) -> list[tuple[Address, GarResolvedUnit]]:
        """DaData-fallback: создаёт GAR-подобные объекты через реальные адреса."""
        from uuid import NAMESPACE_URL, uuid5
        dadata = DadataClient()
        result: list[tuple[Address, GarResolvedUnit]] = []

        for region_code, city_hint, queries in self._GAR_FALLBACK_QUERIES:
            region_name = {
                '01': 'Республика Адыгея',
                '77': 'Москва',
                '38': 'Иркутская область',
            }.get(region_code, f'Регион {region_code}')

            for query in queries:
                address = self._address_from_dadata(dadata, query)
                if not address:
                    continue

                house = address.house
                street = house.street
                city = street.city

                # Строим GarResolvedUnit из данных DaData чтобы title/enrichment работали одинаково
                unit = GarResolvedUnit(
                    region_code=region_code,
                    region_name=region_name,
                    city_guid=city.external_id or uuid5(NAMESPACE_URL, f'dadata-city:{city.name}'),
                    city_name=city.name,
                    street_guid=street.external_id or uuid5(NAMESPACE_URL, f'dadata-street:{city.name}:{street.name}'),
                    street_name=street.name,
                    street_type=street.street_type or 'ул.',
                    house_guid=house.external_id or uuid5(NAMESPACE_URL, f'dadata-house:{street.name}:{house.house_number}'),
                    house_number=house.house_number,
                    apartment_number=address.apartment_number or None,
                )
                result.append((address, unit))

                if len(result) >= len(self._GAR_FALLBACK_QUERIES) * self._GAR_EXTRA_PER_REGION:
                    return result

        return result

    # ------------------------------------------------------------------
    # Создание 20 объектов
    # ------------------------------------------------------------------

    # Спецификации иркутских объектов: (суффикс заголовка, op_code, status_code, price, rooms, area, floor, total_floors)
    _IRKUTSK_SPECS = [
        ('Студия у набережной',    'sale', 'active',   5_200_000, 1, Decimal('31.50'),  3,  9),
        ('2-комн. с ремонтом',     'sale', 'active',   8_700_000, 2, Decimal('52.00'),  6, 16),
        ('3-комн. семейная',       'sale', 'reserved', 12_300_000, 3, Decimal('76.50'), 10, 12),
        ('Студия в аренду',        'rent', 'active',      34_000, 1, Decimal('28.00'),  2,  9),
        ('2-комн. аренда, центр',  'rent', 'active',      56_000, 2, Decimal('47.50'),  5, 10),
    ]

    def _seed_demo_properties(self, addresses: list[Address]) -> list[Property]:
        sale = OperationType.objects.get(code='sale')
        rent = OperationType.objects.get(code='rent')
        op_map = {'sale': sale, 'rent': rent}

        status_active = PropertyStatus.objects.get(code='active')
        status_reserved = PropertyStatus.objects.get(code='reserved')
        status_map = {'active': status_active, 'reserved': status_reserved}

        features = list(PropertyFeature.objects.order_by('name')[:8])
        created: list[Property] = []

        # ── 5 иркутских объектов ─────────────────────────────────────
        self.log.info('   Создаём 5 иркутских объектов...')
        for idx, (suffix, op_code, st_code, price, rooms, area, floor, total_floors) in enumerate(
            self._IRKUTSK_SPECS, start=1
        ):
            address = addresses[idx - 1] if idx - 1 < len(addresses) else addresses[-1]
            city_name = address.house.street.city.name if (
                address.house and address.house.street and address.house.street.city
            ) else 'Иркутск'
            title = f'{city_name} — {suffix}'

            query_address = (
                f'{city_name}, '
                f'{address.house.street.street_type or ""} '
                f'{address.house.street.name}, '
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
                    'description': (
                        f'Объект в г. {city_name}. '
                        'Создан командой seed_data. __seed_demo__'
                    ),
                },
            )
            PropertyFeatureValue.objects.filter(property=property_obj).delete()
            for feature in features[idx - 1: idx + 2]:
                PropertyFeatureValue.objects.create(property=property_obj, feature=feature, value='да')

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

        # ── 15 GAR-объектов из 3 регионов ────────────────────────────
        self.log.info('   Загружаем 15 GAR-объектов из регионов 02/50/66...')
        gar_pairs = self._seed_gar_extra_addresses()

        for gar_idx, (address, unit) in enumerate(gar_pairs, start=1):
            global_idx = 5 + gar_idx
            rooms = 1 + ((gar_idx - 1) % 3)
            area = Decimal('28.00') + Decimal((gar_idx - 1) * 7)
            operation_type = sale if gar_idx % 3 else rent
            status = status_reserved if gar_idx % 5 == 0 else status_active
            price = self._gar_price(index=gar_idx, rooms=rooms, operation_code=operation_type.code)
            street_label = f'{unit.street_type or ""} {unit.street_name}'.strip()
            apt_suffix = f', кв. {unit.apartment_number}' if unit.apartment_number else ''
            title = f'{unit.city_name}, {street_label}, д. {unit.house_number}{apt_suffix}'
            property_obj, _ = Property.objects.update_or_create(
                title=title,
                defaults={
                    'operation_type': operation_type,
                    'status': status,
                    'address': address,
                    'price': price,
                    'price_per_sqm': round(price / float(area), 2),
                    'area_total': area,
                    'rooms_count': rooms,
                    'floor_number': None,
                    'total_floors': None,
                    'description': (
                        f'Объект по данным GAR/FIAS, регион: {unit.region_name}. '
                        '__seed_demo__'
                    ),
                },
            )
            PropertyFeatureValue.objects.filter(property=property_obj).delete()
            for feature in features[(gar_idx - 1) % max(len(features), 1): (gar_idx - 1) % max(len(features), 1) + 3]:
                PropertyFeatureValue.objects.create(property=property_obj, feature=feature, value='да')

            PropertyPhoto.objects.filter(property=property_obj).delete()
            gar_query = f'{unit.city_name}, {street_label}, д. {unit.house_number}'
            enriched = self._enrich_property_from_twogis(
                property_obj,
                address_query=gar_query,
                city=unit.city_name,
            )
            if not enriched:
                PropertyPhoto.objects.create(
                    property=property_obj,
                    image=f'2026/04/{((gar_idx - 1) % 5) + 1}.jpg',
                    caption=f'Фото объекта (GAR) №{gar_idx}',
                    is_cover=True,
                    order=0,
                )
            created.append(property_obj)
            self.log.info(f'   [{global_idx}/20] {title}')

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
                'title': 'Оформить договор аренды ст��дии',
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

    def _enrich_property_from_twogis(
        self,
        property_obj: 'Property',
        *,
        address_query: str,
        city: str = '',
    ) -> bool:
        """Обогащает объект недвижимости данными из 2GIS.

        Если API возвращает результат — обновляет описание и добавляет фото.
        Метод никогда не выбрасывает исключений: ошибки логируются и
        возвращается ``False``, чтобы вызывающий код мог использовать
        локальную заглушку.
        """
        try:
            client = TwoGisClient()
            if not client.api_key:
                return False

            info = client.search_by_address(address_query, city=city)
            if not info:
                return False

            # Координаты
            lat = info.get('lat')
            lon = info.get('lon')
            if lat and lon:
                property_obj.coordinates_lat = lat
                property_obj.coordinates_lon = lon
                property_obj.save(update_fields=['coordinates_lat', 'coordinates_lon'])

            # Описание из 2GIS — обновляем если пришло не пустым
            twogis_desc = (info.get('description') or '').strip()
            if twogis_desc:
                property_obj.description = (
                    twogis_desc + '\n\n' + (property_obj.description or '')
                ).strip()
                property_obj.save(update_fields=['description'])

            # Карты-фото: строятся по координатам через Static Maps API
            photo_urls: list[str] = info.get('photos') or []
            if photo_urls:
                # Удаляем старые записи (уже удалены перед вызовом, но на всякий случай)
                PropertyPhoto.objects.filter(property=property_obj).delete()
                for order, url in enumerate(photo_urls):
                    PropertyPhoto.objects.create(
                        property=property_obj,
                        url=url,
                        caption='Карта 2GIS',
                        is_cover=(order == 0),
                        order=order,
                    )
                self.log.info(
                    f'   2GIS: {len(photo_urls)} карты для «{property_obj.title}»'
                    f' (lat={lat}, lon={lon}).',
                )
                return True

            self.log.warning(
                f'   2GIS: нет координат для «{property_obj.title}» (q={address_query!r}).',
            )
            return False

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                '2GIS обогащение объекта pk=%s (%r) не удалось: %s',
                property_obj.pk, address_query, exc,
            )
            return False

    @staticmethod
    def _gar_price(*, index: int, rooms: int, operation_code: str) -> float:
        if operation_code == 'rent':
            return float(32_000 + rooms * 8_000 + index * 2_500)
        return float(4_500_000 + rooms * 1_250_000 + index * 185_000)

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
