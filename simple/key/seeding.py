"""Общий слой заполнения справочников и тестовых данных."""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .twogis import TwoGisClient, apply_property_enrichment
from .dadata import DadataClient
from .models import (
    Address,
    City,
    ClientCompanyDetails,
    ClientIndividualDetails,
    ClientProfile,
    Deal,
    EmployeeProfile,
    House,
    OperationType,
    Property,
    PropertyType,
    TaskPriority,
    TaskType,
    ClientKind,
    ContactMethod,
    ContractStatus,
    UserType,
    PropertyExternalSource,
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

LOOKUP_TABLES = [
    (PropertyType, [
        {'code': 'apartment', 'name': 'Квартира'},
        {'code': 'house', 'name': 'Дом'},
        {'code': 'office', 'name': 'Офис'},
        {'code': 'warehouse', 'name': 'Склад'},
    ]),
    (TaskPriority, [
        {'code': 'low', 'name': 'Низкий'},
        {'code': 'normal', 'name': 'Обычный'},
        {'code': 'high', 'name': 'Высокий'},
    ]),
    (TaskType, [
        {'code': 'contact_client', 'name': 'Связаться с клиентом'},
        {'code': 'property_search', 'name': 'Подбор объектов'},
        {'code': 'showing', 'name': 'Показ объекта'},
        {'code': 'documents', 'name': 'Подготовка документов'},
        {'code': 'call', 'name': 'Звонок'},
        {'code': 'other', 'name': 'Прочее'},
    ]),
    (ClientKind, [
        {'code': 'individual', 'name': 'Физическое лицо'},
        {'code': 'company', 'name': 'Юридическое лицо'},
    ]),
    (ContactMethod, [
        {'code': 'phone', 'name': 'Телефон'},
        {'code': 'email', 'name': 'Email'},
        {'code': 'whatsapp', 'name': 'WhatsApp'},
        {'code': 'telegram', 'name': 'Telegram'},
    ]),
    (ContractStatus, [
        {'code': 'not_requested', 'name': 'Не запрошен'},
        {'code': 'pending', 'name': 'В очереди'},
        {'code': 'processing', 'name': 'Формируется'},
        {'code': 'ready', 'name': 'Готов'},
        {'code': 'failed', 'name': 'Ошибка'},
    ]),
    (UserType, [
        {'code': 'employee', 'name': 'Сотрудник'},
        {'code': 'client', 'name': 'Клиент'},
    ]),
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
        for model, rows in LOOKUP_TABLES:
            created_counts[str(model._meta.verbose_name_plural)] = self._seed_rows(
                model,
                rows,
                key='code',
            )
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

        stats = {
            'users': {'created': 0, 'updated': 0},
            'properties': {'created': 0, 'updated': 0},
            'requests': {'created': 0, 'updated': 0},
            'tasks': {'created': 0, 'updated': 0},
            'deals': {'created': 0, 'updated': 0},
        }

        users, user_stats = self._seed_real_users()
        stats['users'] = user_stats
        self.log.success(
            f"   Пользователи: создано {user_stats['created']}, обновлено {user_stats['updated']}."
        )

        properties, property_stats = self._seed_real_properties(users)
        stats['properties'] = property_stats
        self.log.success(
            f"   Объекты: создано {property_stats['created']}, обновлено {property_stats['updated']}."
        )

        requests, request_stats = self._seed_real_requests(users, properties)
        stats['requests'] = request_stats
        self.log.success(
            f"   Заявки: создано {request_stats['created']}, обновлено {request_stats['updated']}."
        )

        tasks, task_stats = self._seed_real_tasks(users, properties, requests)
        stats['tasks'] = task_stats
        self.log.success(
            f"   Задачи: создано {task_stats['created']}, обновлено {task_stats['updated']}."
        )

        deals, deal_stats = self._seed_real_deals(users, properties, requests)
        stats['deals'] = deal_stats
        self.log.success(
            f"   Сделки: создано {deal_stats['created']}, обновлено {deal_stats['updated']}."
        )

        self.log.info('')
        self.log.success('Реалистичные CRM-данные готовы. Логины пользователей:')
        for user in users.values():
            role = user.role.name if user.role_id else 'клиент'
            self.log.info(
                f'    {user.username:<24} ({user.user_type:<8}, роль: {role}) пароль: RealPass123!',
            )
        return stats

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

    @staticmethod
    def _bump_stat(stats: dict[str, int], created: bool) -> None:
        stats['created' if created else 'updated'] += 1

    @staticmethod
    def _set_model_dates(model, pk, **dates) -> None:
        clean_dates = {key: value for key, value in dates.items() if value is not None}
        if clean_dates:
            model.objects.filter(pk=pk).update(**clean_dates)

    @staticmethod
    def _get_by_code(model, code: str):
        return model.objects.get(code=code)

    def _seed_real_users(self) -> tuple[dict[str, User], dict[str, int]]:
        password = 'RealPass123!'
        stats = {'created': 0, 'updated': 0}
        roles = {
            'admin': UserRole.objects.get(code='admin'),
            'manager': UserRole.objects.get(code='manager'),
            'agent': UserRole.objects.get(code='agent'),
        }

        employees = [
            ('ivanov.artem', 'artem.ivanov@realty-crm.ru', '+79001111111', 'admin', 'Иванов', 'Артём', 'Дмитриевич', 'Системный администратор', 6),
            ('petrova.ekaterina', 'ekaterina.petrova@realty-crm.ru', '+79002222222', 'admin', 'Петрова', 'Екатерина', 'Андреевна', 'Руководитель отдела', 8),
            ('kozlov.dmitry', 'dmitry.kozlov@realty-crm.ru', '+79003333333', 'manager', 'Козлов', 'Дмитрий', 'Сергеевич', 'Старший модератор', 5),
            ('sokolova.anna', 'anna.sokolova@realty-crm.ru', '+79004444444', 'manager', 'Соколова', 'Анна', 'Владимировна', 'Модератор объектов', 3),
            ('smirnov.alexey', 'alexey.smirnov@realty-crm.ru', '+79005555551', 'agent', 'Смирнов', 'Алексей', 'Игоревич', 'Агент по продаже, жилая недвижимость', 8),
            ('volkova.maria', 'maria.volkova@realty-crm.ru', '+79005555552', 'agent', 'Волкова', 'Мария', 'Павловна', 'Агент по продаже, коммерческая недвижимость', 5),
            ('orlov.nikita', 'nikita.orlov@realty-crm.ru', '+79005555553', 'agent', 'Орлов', 'Никита', 'Алексеевич', 'Агент по продаже, загородная недвижимость', 2),
            ('morozova.irina', 'irina.morozova@realty-crm.ru', '+79006666661', 'agent', 'Морозова', 'Ирина', 'Викторовна', 'Агент по аренде жилья', 7),
            ('egorov.pavel', 'pavel.egorov@realty-crm.ru', '+79006666662', 'agent', 'Егоров', 'Павел', 'Николаевич', 'Агент по аренде коммерческой недвижимости', 4),
            ('lebedeva.olga', 'olga.lebedeva@realty-crm.ru', '+79006666663', 'agent', 'Лебедева', 'Ольга', 'Сергеевна', 'Агент по аренде загородных объектов', 3),
            ('fedorov.roman', 'roman.fedorov@realty-crm.ru', '+79007777771', 'manager', 'Фёдоров', 'Роман', 'Андреевич', 'Менеджер по работе с клиентами', 4),
            ('nikitina.alena', 'alena.nikitina@realty-crm.ru', '+79007777772', 'manager', 'Никитина', 'Алёна', 'Михайловна', 'Менеджер по работе с клиентами', 2),
        ]

        individuals = [
            ('kuznetsov.sergey', 'sergey.kuznetsov@mail.ru', '+79008880001', 'Кузнецов', 'Сергей', 'Олегович', 'phone', 'Предпочитает утренние звонки.'),
            ('vasilieva.natalia', 'natalia.vasilieva@yandex.ru', '+79008880002', 'Васильева', 'Наталья', 'Петровна', 'whatsapp', 'Просит отправлять подборки в WhatsApp.'),
            ('mikhailov.igor', 'igor.mikhailov@gmail.com', '+79008880003', 'Михайлов', 'Игорь', 'Станиславович', 'email', 'Сравнивает варианты для инвестиций.'),
            ('romanova.elena', 'elena.romanova@mail.ru', '+79008880004', 'Романова', 'Елена', 'Игоревна', 'phone', 'Нужен спокойный район и школа рядом.'),
            ('andreev.maxim', 'maxim.andreev@yandex.ru', '+79008880005', 'Андреев', 'Максим', 'Юрьевич', 'whatsapp', 'Готов к просмотрам вечером после работы.'),
            ('zaitseva.daria', 'daria.zaitseva@gmail.com', '+79008880006', 'Зайцева', 'Дарья', 'Александровна', 'email', 'Интересуют только квартиры с ремонтом.'),
            ('pavlov.kirill', 'kirill.pavlov@mail.ru', '+79008880007', 'Павлов', 'Кирилл', 'Денисович', 'phone', 'Покупает объект для родителей.'),
            ('belova.oksana', 'oksana.belova@yandex.ru', '+79008880008', 'Белова', 'Оксана', 'Владимировна', 'whatsapp', 'Не звонить до 11:00.'),
            ('nikolaev.artur', 'artur.nikolaev@gmail.com', '+79008880009', 'Николаев', 'Артур', 'Романович', 'email', 'Нужна ипотечная сделка.'),
            ('grigorieva.sofia', 'sofia.grigorieva@mail.ru', '+79008880010', 'Григорьева', 'София', 'Максимовна', 'phone', 'Ищет аренду на длительный срок.'),
        ]

        companies = [
            ('baikal.logistic', 'office@baikal-logistic.ru', '+79009990001', 'ООО Байкал Логистик', '3811456723', 'Иркутск, ул. Рабочая, д. 18', 'Иркутск, ул. Рабочая, д. 18'),
            ('angara.dev', 'contact@angara-dev.ru', '+79009990002', 'ООО Ангара Девелопмент', '7704567812', 'Москва, Пресненская наб., д. 10', 'Москва, Пресненская наб., д. 10'),
            ('east.trade', 'info@east-trade.ru', '+79009990003', 'ООО Восток Трейд', '2723456781', 'Хабаровск, ул. Муравьёва-Амурского, д. 25', 'Хабаровск, ул. Муравьёва-Амурского, д. 25'),
            ('transbaikalia.retail', 'admin@transbaikalia-retail.ru', '+79009990004', 'ООО Забайкалье Ритейл', '7536123456', 'Чита, ул. Ленина, д. 88', 'Чита, ул. Ленина, д. 88'),
            ('siberia.service', 'hello@siberia-service.ru', '+79009990005', 'ООО Сибирский Сервис', '3808123450', 'Иркутск, ул. Байкальская, д. 105', 'Иркутск, ул. Байкальская, д. 107'),
        ]

        users: dict[str, User] = {}
        for username, email, phone, role_code, last_name, first_name, middle_name, position, experience in employees:
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    'email': email,
                    'phone': phone,
                    'user_type': 'employee',
                    'role': roles[role_code],
                    'is_staff': True,
                    'is_active': True,
                    'is_email_verified': True,
                    'is_phone_verified': True,
                },
            )
            user.set_password(password)
            user.save(update_fields=['password'])
            hire_date = timezone.localdate() - timedelta(days=365 * experience)
            EmployeeProfile.objects.update_or_create(
                user=user,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'middle_name': middle_name,
                    'position': position,
                    'hire_date': hire_date,
                    'internal_phone': phone[-4:],
                },
            )
            users[username] = user
            self._bump_stat(stats, created)

        for index, (username, email, phone, last_name, first_name, middle_name, contact, note) in enumerate(individuals, start=1):
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    'email': email,
                    'phone': phone,
                    'user_type': 'client',
                    'role': None,
                    'is_staff': False,
                    'is_active': True,
                    'is_email_verified': True,
                    'is_phone_verified': True,
                },
            )
            user.set_password(password)
            user.save(update_fields=['password'])
            profile, _ = ClientProfile.objects.update_or_create(
                user=user,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'middle_name': middle_name,
                    'client_kind': 'individual',
                    'preferred_contact_method': contact,
                    'notes': note,
                },
            )
            ClientIndividualDetails.objects.update_or_create(
                profile=profile,
                defaults={
                    'passport_series': f'{3800 + index:04d}',
                    'passport_number': f'{120000 + index:06d}',
                    'passport_issued_by': 'ГУ МВД России по Иркутской области',
                    'passport_issued_date': date(2018 + (index % 5), (index % 12) + 1, min(index + 3, 28)),
                    'passport_code': f'380-{100 + index:03d}',
                },
            )
            users[username] = user
            self._bump_stat(stats, created)

        for username, email, phone, company_name, inn, registration_address, actual_address in companies:
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    'email': email,
                    'phone': phone,
                    'user_type': 'client',
                    'role': None,
                    'is_staff': False,
                    'is_active': True,
                    'is_email_verified': True,
                    'is_phone_verified': True,
                },
            )
            user.set_password(password)
            user.save(update_fields=['password'])
            profile, _ = ClientProfile.objects.update_or_create(
                user=user,
                defaults={
                    'first_name': company_name,
                    'last_name': 'Компания',
                    'middle_name': '',
                    'client_kind': 'company',
                    'preferred_contact_method': 'email',
                    'registration_address': registration_address,
                    'actual_address': actual_address,
                    'notes': 'Корпоративный клиент, согласование через бухгалтерию.',
                },
            )
            ClientCompanyDetails.objects.update_or_create(
                profile=profile,
                defaults={'company_inn': inn},
            )
            users[username] = user
            self._bump_stat(stats, created)

        return users, stats

    def _real_house(self, city_name: str, region: str, street_name: str, street_type: str, house_number: str, postal_code: str | None = None) -> House:
        city, _ = City.objects.update_or_create(
            name=city_name,
            defaults={'region': region},
        )
        street, _ = Street.objects.update_or_create(
            city=city,
            name=street_name,
            defaults={'street_type': street_type},
        )
        house, _ = House.objects.update_or_create(
            street=street,
            house_number=str(house_number),
            defaults={'postal_code': postal_code},
        )
        return house

    def _seed_real_properties(self, users: dict[str, User]) -> tuple[list[Property], dict[str, int]]:
        stats = {'created': 0, 'updated': 0}
        op = {item.code: item for item in OperationType.objects.all()}
        status = {item.code: item for item in PropertyStatus.objects.all()}
        owners = [
            users['kuznetsov.sergey'], users['vasilieva.natalia'], users['mikhailov.igor'],
            users['romanova.elena'], users['andreev.maxim'], users['zaitseva.daria'],
            users['pavlov.kirill'], users['belova.oksana'], users['nikolaev.artur'],
            users['grigorieva.sofia'], users['baikal.logistic'], users['angara.dev'],
            users['east.trade'], users['transbaikalia.retail'], users['siberia.service'],
        ]
        photo_base = [
            'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2',
            'https://images.unsplash.com/photo-1560184897-ae75f418493e',
            'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85',
            'https://images.unsplash.com/photo-1494526585095-c41746248156',
            'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab',
        ]
        specs = self._real_property_specs()
        properties: list[Property] = []
        now = timezone.now()

        for index, spec in enumerate(specs, start=1):
            house = self._real_house(
                spec['city'],
                spec['region'],
                spec['street'],
                spec.get('street_type', 'ул.'),
                spec['house'],
                spec.get('postal_code'),
            )
            defaults = {
                'operation_type': op[spec['operation']],
                'status': status[spec['status']],
                'house': house,
                'owner': owners[(index - 1) % len(owners)],
                'coordinates_lat': Decimal(str(spec['lat'])),
                'coordinates_lon': Decimal(str(spec['lon'])),
                'premises_type': spec['type'],
                'price': float(spec['price']),
                'area_total': Decimal(str(spec['area'])),
                'rooms_count': spec.get('rooms'),
                'floor_number': spec.get('floor'),
                'total_floors': spec.get('floors'),
                'description': spec['description'],
            }
            property_obj, created = Property.objects.update_or_create(
                title=spec['title'],
                house=house,
                defaults=defaults,
            )
            PropertyExternalSource.objects.update_or_create(
                property=property_obj,
                source_name='2gis',
                external_id=f'2gis-real-{index:04d}',
                defaults={
                    'source_object_name': spec['title'],
                    'source_address': f"{spec['city']}, {spec.get('street_type', 'ул.')} {spec['street']}, д. {spec['house']}",
                    'source_rubric': spec['rubric'],
                    'synced_at': now - timedelta(days=index % 12),
                },
            )
            PropertyPhoto.objects.filter(property=property_obj).delete()
            photo_count = 2 + (index % 4)
            for order in range(photo_count):
                PropertyPhoto.objects.create(
                    property=property_obj,
                    url=f"{photo_base[(index + order) % len(photo_base)]}?auto=format&fit=crop&w=1200&q=80&sig={index}-{order}",
                    caption=f'Фото {order + 1}: {spec["title"]}',
                    is_cover=(order == 0),
                    order=order,
                )
            self._set_model_dates(
                Property,
                property_obj.pk,
                created_at=now - timedelta(days=80 - index),
                updated_at=now - timedelta(days=max(1, 20 - (index % 18))),
            )
            property_obj.refresh_from_db()
            properties.append(property_obj)
            self._bump_stat(stats, created)
        return properties, stats

    def _real_property_specs(self) -> list[dict]:
        common = {
            'Иркутск': ('Иркутская область', '664000'),
            'Москва': ('Москва', '101000'),
            'Хабаровск': ('Хабаровский край', '680000'),
            'Чита': ('Забайкальский край', '672000'),
        }
        rows = [
            ('Иркутск', 'Ленина', '1', 'Квартира с видом на Ангару', 'sale', 'active', 'apartment', 9200000, 58.4, 2, 5, 9, '52.286974', '104.280660'),
            ('Иркутск', 'Карла Маркса', '23', 'Семейная трёхкомнатная в центре', 'sale', 'reserved', 'apartment', 12800000, 81.2, 3, 7, 12, '52.285780', '104.291420'),
            ('Иркутск', 'Байкальская', '105', 'Офис open space на Байкальской', 'rent', 'active', 'office', 185000, 142.0, None, 3, 7, '52.267010', '104.333720'),
            ('Иркутск', 'Депутатская', '45', 'Таунхаус для семьи у зелёной зоны', 'sale', 'active', 'house', 23600000, 168.5, 5, None, 2, '52.255830', '104.315120'),
            ('Иркутск', 'Рабочая', '18', 'Складской блок у транспортной развязки', 'rent', 'rented', 'warehouse', 240000, 520.0, None, None, None, '52.304110', '104.256810'),
            ('Иркутск', 'Советская', '55', 'Компактная квартира для аренды', 'rent', 'active', 'apartment', 43000, 34.8, 1, 4, 9, '52.274330', '104.307120'),
            ('Иркутск', 'Лермонтова', '79', 'Двухкомнатная рядом с университетом', 'sale', 'sold', 'apartment', 7600000, 47.9, 2, 6, 10, '52.246860', '104.269410'),
            ('Иркутск', 'Седова', '40', 'Кирпичный дом с участком', 'sale', 'archived', 'house', 18400000, 132.0, 4, None, 2, '52.273980', '104.287520'),
            ('Иркутск', 'Красноярская', '11', 'Помещение под шоурум', 'rent', 'active', 'office', 115000, 86.0, None, 1, 5, '52.276510', '104.296730'),
            ('Иркутск', 'Трилиссера', '8', 'Светлая студия в новом доме', 'sale', 'active', 'apartment', 5100000, 29.7, 1, 8, 16, '52.275420', '104.318900'),
            ('Москва', 'Тверская', '12', 'Апартаменты на Тверской', 'sale', 'active', 'apartment', 48500000, 74.5, 3, 9, 14, '55.761590', '37.609460'),
            ('Москва', 'Арбат', '24', 'Историческая квартира на Арбате', 'sale', 'reserved', 'apartment', 62200000, 91.0, 3, 4, 7, '55.749910', '37.590230'),
            ('Москва', 'Кутузовский проспект', '30', 'Представительский офис у метро', 'rent', 'active', 'office', 680000, 210.0, None, 8, 18, '55.741260', '37.535950'),
            ('Москва', 'Ленинский проспект', '64', 'Большая квартира для семьи', 'sale', 'sold', 'apartment', 54800000, 104.2, 4, 12, 20, '55.700940', '37.570970'),
            ('Москва', 'Профсоюзная', '45', 'Склад last mile на юго-западе', 'rent', 'rented', 'warehouse', 720000, 860.0, None, None, None, '55.666590', '37.552250'),
            ('Москва', 'Пресненская набережная', '10', 'Офис в Москва-Сити', 'rent', 'active', 'office', 1250000, 248.0, None, 32, 65, '55.749740', '37.537050'),
            ('Москва', 'Малая Никитская', '18', 'Клубный дом в тихом переулке', 'sale', 'active', 'apartment', 73800000, 118.0, 4, 5, 8, '55.756370', '37.593490'),
            ('Москва', 'Садовая-Самотёчная', '7', 'Квартира для долгосрочной аренды', 'rent', 'active', 'apartment', 210000, 62.3, 2, 6, 12, '55.771560', '37.614760'),
            ('Москва', 'Большая Якиманка', '32', 'Пентхаус с террасой', 'sale', 'active', 'apartment', 146000000, 184.0, 5, 14, 15, '55.737840', '37.612430'),
            ('Москва', 'Варшавское шоссе', '125', 'Складской комплекс у МКАД', 'sale', 'archived', 'warehouse', 98000000, 1240.0, None, None, None, '55.610140', '37.607770'),
            ('Хабаровск', 'Муравьёва-Амурского', '25', 'Квартира в историческом центре', 'sale', 'active', 'apartment', 11200000, 66.0, 3, 5, 9, '48.472550', '135.057600'),
            ('Хабаровск', 'Ленина', '38', 'Офис у площади Ленина', 'rent', 'active', 'office', 160000, 118.0, None, 2, 6, '48.480290', '135.068750'),
            ('Хабаровск', 'Карла Маркса', '90', 'Семейная квартира с лоджией', 'sale', 'reserved', 'apartment', 9400000, 72.4, 3, 8, 12, '48.498270', '135.086780'),
            ('Хабаровск', 'Амурский бульвар', '46', 'Дом недалеко от набережной', 'sale', 'sold', 'house', 18600000, 148.0, 5, None, 2, '48.484950', '135.061140'),
            ('Хабаровск', 'Тургенева', '55', 'Склад для региональной доставки', 'rent', 'rented', 'warehouse', 310000, 610.0, None, None, None, '48.469220', '135.072980'),
            ('Чита', 'Ленина', '88', 'Квартира в центре Читы', 'sale', 'active', 'apartment', 7200000, 54.0, 2, 4, 9, '52.033800', '113.499420'),
            ('Чита', 'Амурская', '36', 'Помещение под аптеку', 'rent', 'active', 'office', 95000, 74.0, None, 1, 5, '52.035620', '113.505310'),
            ('Чита', 'Бабушкина', '64', 'Дом с тёплым гаражом', 'sale', 'reserved', 'house', 12800000, 126.0, 4, None, 2, '52.026180', '113.520910'),
            ('Чита', 'Чкалова', '149', 'Трёхкомнатная для большой семьи', 'sale', 'sold', 'apartment', 8100000, 69.3, 3, 6, 10, '52.030240', '113.513480'),
            ('Чита', 'Костюшко-Григоровича', '5', 'Склад у железнодорожной ветки', 'rent', 'archived', 'warehouse', 180000, 430.0, None, None, None, '52.041180', '113.492610'),
        ]
        specs = []
        for city, street, house, title, operation, status, p_type, price, area, rooms, floor, floors, lat, lon in rows:
            region, postal_code = common[city]
            if p_type == 'warehouse':
                rubric = 'Складская недвижимость'
            elif p_type == 'office':
                rubric = 'Офисная недвижимость'
            elif p_type == 'house':
                rubric = 'Загородная недвижимость'
            else:
                rubric = 'Жилая недвижимость'
            description = (
                f'{title} расположен в востребованной части города {city}. '
                'Объект подходит для спокойного проживания или устойчивой инвестиции. '
                'Планировка продумана, основные коммуникации и инфраструктура находятся рядом. '
                'Документы готовы к проверке, показ можно согласовать в удобное время.'
            )
            specs.append({
                'city': city,
                'region': region,
                'street': street,
                'street_type': 'ул.' if 'проспект' not in street.lower() and 'шоссе' not in street.lower() and 'набережная' not in street.lower() else '',
                'house': house,
                'postal_code': postal_code,
                'title': title,
                'operation': operation,
                'status': status,
                'type': p_type,
                'price': price,
                'area': area,
                'rooms': rooms,
                'floor': floor,
                'floors': floors,
                'lat': lat,
                'lon': lon,
                'rubric': rubric,
                'description': description,
            })
        return specs

    def _seed_real_requests(self, users: dict[str, User], properties: list[Property]) -> tuple[list[Request], dict[str, int]]:
        stats = {'created': 0, 'updated': 0}
        statuses = {item.code: item for item in RequestStatus.objects.all()}
        agents = [
            users['smirnov.alexey'], users['volkova.maria'], users['orlov.nikita'],
            users['morozova.irina'], users['egorov.pavel'], users['lebedeva.olga'],
            users['fedorov.roman'], users['nikitina.alena'],
        ]
        clients = [
            users['kuznetsov.sergey'], users['vasilieva.natalia'], users['mikhailov.igor'],
            users['romanova.elena'], users['andreev.maxim'], users['zaitseva.daria'],
            users['pavlov.kirill'], users['belova.oksana'], users['nikolaev.artur'],
            users['grigorieva.sofia'], users['baikal.logistic'], users['angara.dev'],
            users['east.trade'], users['transbaikalia.retail'], users['siberia.service'],
        ]
        now = timezone.now()
        requests: list[Request] = []
        for index in range(15):
            property_obj = properties[index * 2] if index % 4 != 3 else None
            operation = property_obj.operation_type if property_obj else OperationType.objects.get(code='sale' if index % 2 == 0 else 'rent')
            status_code = [
                'open', 'processing', 'completed', 'cancelled', 'completed',
                'processing', 'open', 'completed', 'cancelled', 'completed',
                'processing', 'open', 'completed', 'processing', 'cancelled',
            ][index]
            created_at = now - timedelta(days=86 - index * 5)
            closed_at = created_at + timedelta(days=12) if status_code in Request.TERMINAL_STATUS_CODES else None
            description = [
                'Клиент хочет сравнить несколько вариантов перед внесением аванса.',
                'Нужен быстрый просмотр и предварительная проверка документов.',
                'Клиент готов выйти на сделку после согласования условий.',
                'Запрос отменён после изменения бюджета.',
                'Требуется подбор с учётом транспортной доступности.',
            ][index % 5]
            defaults = {
                'agent': agents[index % len(agents)],
                'property': property_obj,
                'operation_type': operation,
                'status': statuses[status_code],
                'property_type': property_obj.premises_type if property_obj else ('office' if index % 3 == 0 else 'apartment'),
                'min_price': float((property_obj.price if property_obj else 5_000_000) * 0.85),
                'max_price': float((property_obj.price if property_obj else 5_000_000) * 1.15),
                'min_area': property_obj.area_total if property_obj else Decimal('40.00'),
                'max_area': (property_obj.area_total + Decimal('25.00')) if property_obj and property_obj.area_total else Decimal('90.00'),
                'rooms_count': property_obj.rooms_count if property_obj and property_obj.rooms_count else (None if index % 3 == 0 else 2),
                'address_preferences': str(property_obj.address) if property_obj else 'Центральные районы, рядом с транспортом',
                'description': description,
                'closed_at': closed_at,
            }
            request_obj, created = Request.objects.update_or_create(
                client=clients[index],
                description=description,
                defaults=defaults,
            )
            self._set_model_dates(
                Request,
                request_obj.pk,
                created_at=created_at,
                updated_at=created_at + timedelta(days=3),
                closed_at=closed_at,
            )
            request_obj.refresh_from_db()
            requests.append(request_obj)
            self._bump_stat(stats, created)
        return requests, stats

    def _seed_real_tasks(self, users: dict[str, User], properties: list[Property], requests: list[Request]) -> tuple[list[Task], dict[str, int]]:
        stats = {'created': 0, 'updated': 0}
        statuses = {item.code: item for item in TaskStatus.objects.all()}
        now = timezone.now()
        task_types = ['call', 'showing', 'property_search', 'documents', 'other']
        priorities = ['high', 'normal', 'normal', 'high', 'low']
        results = {
            'done': 'Клиент получил информацию, следующий шаг согласован.',
            'cancelled': 'Задача отменена после изменения статуса заявки.',
        }
        agents = [
            users['smirnov.alexey'], users['volkova.maria'], users['orlov.nikita'],
            users['morozova.irina'], users['egorov.pavel'], users['lebedeva.olga'],
        ]
        tasks: list[Task] = []
        for index in range(20):
            status_code = ['new', 'in_progress', 'waiting', 'done', 'cancelled'][index % 5]
            request_obj = requests[index % len(requests)]
            property_obj = request_obj.property or properties[index % len(properties)]
            title = f'{index + 1:02d}. {["Позвонить клиенту", "Провести показ", "Подготовить подборку", "Проверить документы", "Обновить карточку"][index % 5]}'
            due_date = now + timedelta(days=(index % 14) + 1)
            completed_at = now - timedelta(days=index % 7, hours=2) if status_code in {'done', 'cancelled'} else None
            defaults = {
                'description': f'Рабочая задача по заявке №{request_obj.pk}: {request_obj.description}',
                'task_type': task_types[index % len(task_types)],
                'priority': priorities[index % len(priorities)],
                'status': statuses[status_code],
                'assignee': agents[index % len(agents)],
                'created_by': users['fedorov.roman'] if index % 2 == 0 else users['nikitina.alena'],
                'client': request_obj.client,
                'property': property_obj,
                'request': request_obj,
                'due_date': due_date,
                'completed_at': completed_at,
                'result': results.get(status_code, ''),
            }
            task_obj, created = Task.objects.update_or_create(
                title=title,
                request=request_obj,
                defaults=defaults,
            )
            self._set_model_dates(
                Task,
                task_obj.pk,
                created_at=now - timedelta(days=25 - index),
                updated_at=now - timedelta(days=max(0, 12 - index % 12)),
            )
            task_obj.refresh_from_db()
            tasks.append(task_obj)
            self._bump_stat(stats, created)
        return tasks, stats

    def _seed_real_deals(self, users: dict[str, User], properties: list[Property], requests: list[Request]) -> tuple[list[Deal], dict[str, int]]:
        stats = {'created': 0, 'updated': 0}
        deal_status = DealStatus.objects.filter(code='completed').first() or DealStatus.objects.filter(code='signed').first() or DealStatus.objects.first()
        completed_requests = [request for request in requests if request.status_code == 'completed'][:5]
        deal_numbers = [f'CRM-2026-{index:04d}' for index in range(1, len(completed_requests) + 1)]
        # Старые версии seed_demo могли привязать эти же номера сделок к другим заявкам.
        Deal.objects.filter(deal_number__in=deal_numbers).update(request=None)
        deals: list[Deal] = []
        for index, request_obj in enumerate(completed_requests, start=1):
            property_obj = request_obj.property or properties[index - 1]
            commission_percent = Decimal(['3.00', '3.50', '4.00', '4.50', '5.00'][index - 1])
            price_final = float(property_obj.price)
            deal_date = timezone.localdate() - timedelta(days=35 - index * 4)
            requested_at = timezone.make_aware(datetime.combine(deal_date, time.min)) + timedelta(hours=10)
            generated_at = requested_at + timedelta(hours=2)
            defaults = {
                'property': property_obj,
                'agent': request_obj.agent or users['smirnov.alexey'],
                'client': request_obj.client,
                'operation_type': property_obj.operation_type,
                'status': deal_status,
                'request': request_obj,
                'price_final': price_final,
                'commission_percent': commission_percent,
                'commission_amount': round(price_final * float(commission_percent) / 100, 2),
                'deal_date': deal_date,
                'notes': 'Сделка закрыта после проверки документов и согласования условий с клиентом.',
                'contract_status': 'ready',
                'contract_requested_at': requested_at,
                'contract_generated_at': generated_at,
            }
            Deal.objects.filter(request=request_obj).exclude(deal_number=f'CRM-2026-{index:04d}').update(request=None)
            deal, created = Deal.objects.update_or_create(
                deal_number=f'CRM-2026-{index:04d}',
                defaults=defaults,
            )
            if not deal.contract_file:
                content = (
                    f'Договор {deal.deal_number}\n'
                    f'Клиент: {deal.client.username}\n'
                    f'Объект: {deal.property.title}\n'
                    f'Сумма сделки: {deal.price_final:.2f}\n'
                ).encode('utf-8')
                deal.contract_file.save(
                    f'contract-{deal.deal_number}.txt',
                    ContentFile(content),
                    save=True,
                )
            deals.append(deal)
            self._bump_stat(stats, created)
        return deals, stats

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

    def _seed_demo_addresses(self) -> list[House]:
        """Создаёт 5 иркутских домов через DaData + fallback на синтетику."""
        dadata = DadataClient()
        addresses: list[House] = []

        for raw_query in self._IRKUTSK_QUERIES:
            address = self._address_from_dadata(dadata, raw_query)
            if address:
                addresses.append(address)

        # Если DaData недоступна — создаём синтетические дома как раньше
        if not addresses:
            self.log.warning('   DaData недоступна — создаём синтетические иркутские дома.')
            addresses = self._seed_synthetic_addresses()

        # Если частично получили дома — добиваем синтетикой до 5
        if len(addresses) < 5:
            synthetic = self._seed_synthetic_addresses()
            addresses += synthetic[:5 - len(addresses)]

        return addresses

    def _address_from_dadata(self, dadata: DadataClient, query: str) -> House | None:
        """Запрашивает один адрес из DaData и создаёт запись House в БД."""
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
            house = House.objects.filter(street=street, house_number=house_number).first()
            if house is None:
                house = House.objects.create(
                    street=street,
                    house_number=house_number,
                    postal_code=s.get('postal_code') or None,
                )

        return house

    def _seed_synthetic_addresses(self) -> list[House]:
        """Синтетические иркутские дома — fallback при отсутствии DaData."""
        city = City.objects.filter(name='Иркутск').first()
        if city is None:
            city = City.objects.create(name='Иркутск', region='Иркутская область')

        street = Street.objects.filter(city=city, name='Ленина').first()
        if street is None:
            street = Street.objects.create(city=city, name='Ленина', street_type='ул.')
        addresses: list[House] = []
        for index in range(1, 6):
            house, _ = House.objects.get_or_create(
                street=street,
                house_number=str(index),
                defaults={'postal_code': '664000'},
            )
            addresses.append(house)
        return addresses

    def _seed_demo_properties(self, addresses: list[House]) -> list[Property]:
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
                defaults={'postal_code': None},
            )
            address = Address.objects.filter(house=house).first()
            if address is None:
                address = Address.objects.create(house=house)

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
                'Помещение в цене'
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
