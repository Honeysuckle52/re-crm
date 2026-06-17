# -*- coding: utf-8 -*-
"""Декларативные наборы данных для seed_data."""
from __future__ import annotations

from decimal import Decimal

from .models import (
    Amenity,
    AuditAction,
    AuditEntityType,
    BathroomType,
    BuildingMaterial,
    ClientKind,
    CommercialPropertyType,
    ContractStatus,
    DealParticipantRole,
    DocumentType,
    PropertyType,
    RenovationType,
    RequestMatchStatus,
    TaskPriority,
    TaskType,
    UserType,
    ViewingStatus,
)


CITY_DATA = {
    'irkutsk': {
        'name': 'Иркутск',
        'region': 'Иркутская область',
        'streets': ['Байкальская', 'Ленина', 'Карла Маркса', 'Советская', 'Депутатская'],
        'lat': Decimal('52.28697400'),
        'lon': Decimal('104.30501800'),
    },
    'moscow': {
        'name': 'Москва',
        'region': 'Москва',
        'streets': ['Тверская', 'Арбат', 'Профсоюзная', 'Ленинский проспект', 'Мосфильмовская'],
        'lat': Decimal('55.75582500'),
        'lon': Decimal('37.61729800'),
    },
    'khabarovsk': {
        'name': 'Хабаровск',
        'region': 'Хабаровский край',
        'streets': ['Муравьева-Амурского', 'Ленина', 'Тургенева', 'Комсомольская', 'Амурский бульвар'],
        'lat': Decimal('48.48022300'),
        'lon': Decimal('135.07191700'),
    },
    'chita': {
        'name': 'Чита',
        'region': 'Забайкальский край',
        'streets': ['Ленина', 'Амурская', 'Бабушкина', 'Чкалова', 'Богомягкова'],
        'lat': Decimal('52.03401200'),
        'lon': Decimal('113.49948800'),
    },
}

OPERATION_TYPES = [
    {'code': 'sale', 'name': 'Продажа'},
    {'code': 'rent', 'name': 'Аренда'},
]

PROPERTY_STATUSES = [
    {'code': 'active', 'name': 'Активно'},
    {'code': 'pending', 'name': 'На модерации'},
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
    {'code': 'new', 'name': 'Новая'},
    {'code': 'in_progress', 'name': 'В работе'},
    {'code': 'closed', 'name': 'Закрыта'},
]

DEAL_STATUSES = [
    {'code': 'draft', 'name': 'Черновик', 'order': 0},
    {'code': 'new', 'name': 'Новая', 'order': 1},
    {'code': 'negotiation', 'name': 'Переговоры', 'order': 2},
    {'code': 'documents', 'name': 'Подготовка документов', 'order': 3},
    {'code': 'signed', 'name': 'Подписана', 'order': 4},
    {'code': 'in_progress', 'name': 'В оформлении', 'order': 5},
    {'code': 'completed', 'name': 'Завершена', 'order': 6},
    {'code': 'cancelled', 'name': 'Отменена', 'order': 7},
]

TASK_STATUSES = [
    {'code': 'new', 'name': 'Новая', 'order': 0},
    {'code': 'in_progress', 'name': 'В работе', 'order': 1},
    {'code': 'waiting', 'name': 'Ожидание', 'order': 2},
    {'code': 'done', 'name': 'Выполнена', 'order': 3},
    {'code': 'cancelled', 'name': 'Отменена', 'order': 4},
    {'code': 'completed', 'name': 'Завершена', 'order': 5},
]

USER_ROLES = [
    {'code': 'client', 'name': 'Клиент', 'description': 'Обычный клиент системы'},
    {'code': 'admin', 'name': 'Администратор', 'description': 'Полный доступ к системе'},
    {'code': 'agent', 'name': 'Агент', 'description': 'Агент по недвижимости'},
    {'code': 'manager', 'name': 'Менеджер', 'description': 'Управление заявками и сделками'},
]

LOOKUP_TABLES = [
    (
        PropertyType,
        [
            {'code': 'apartment', 'name': 'Квартира'},
            {'code': 'house', 'name': 'Дом/Коттедж'},
            {'code': 'commercial', 'name': 'Коммерческая'},
            {'code': 'land', 'name': 'Земельный участок'},
            {'code': 'garage', 'name': 'Гараж'},
            {'code': 'room', 'name': 'Комната'},
        ],
    ),
    (
        TaskPriority,
        [
            {'code': 'low', 'name': 'Низкий'},
            {'code': 'medium', 'name': 'Средний'},
            {'code': 'high', 'name': 'Высокий'},
            {'code': 'urgent', 'name': 'Срочный'},
            {'code': 'normal', 'name': 'Обычный'},
        ],
    ),
    (
        TaskType,
        [
            {'code': 'call_client', 'name': 'Позвонить клиенту'},
            {'code': 'show_property', 'name': 'Показать объект'},
            {'code': 'property_search', 'name': 'Подбор объектов'},
            {'code': 'prepare_docs', 'name': 'Подготовить документы'},
            {'code': 'negotiate', 'name': 'Провести переговоры'},
            {'code': 'other', 'name': 'Другое'},
            {'code': 'sign_contract', 'name': 'Подписать договор'},
            {'code': 'contact_client', 'name': 'Связаться с клиентом'},
            {'code': 'showing', 'name': 'Показ объекта'},
            {'code': 'documents', 'name': 'Документы'},
            {'code': 'call', 'name': 'Звонок'},
        ],
    ),
    (
        ClientKind,
        [
            {'code': 'individual', 'name': 'Физическое лицо'},
            {'code': 'company', 'name': 'Юридическое лицо'},
        ],
    ),
    (
        ContractStatus,
        [
            {'code': 'draft', 'name': 'Черновик'},
            {'code': 'pending', 'name': 'На согласовании'},
            {'code': 'signed', 'name': 'Подписан'},
            {'code': 'rejected', 'name': 'Отклонен'},
            {'code': 'processing', 'name': 'Формируется'},
            {'code': 'ready', 'name': 'Готов'},
            {'code': 'failed', 'name': 'Ошибка'},
            {'code': 'not_requested', 'name': 'Не запрошен'},
        ],
    ),
    (
        UserType,
        [
            {'code': 'employee', 'name': 'Сотрудник'},
            {'code': 'client', 'name': 'Клиент'},
        ],
    ),
    (
        RenovationType,
        [
            {'code': 'none', 'name': 'Без ремонта'},
            {'code': 'cosmetic', 'name': 'Косметический'},
            {'code': 'euro', 'name': 'Евроремонт'},
            {'code': 'designer', 'name': 'Дизайнерский'},
        ],
    ),
    (
        BathroomType,
        [
            {'code': 'combined', 'name': 'Совмещенный'},
            {'code': 'separate', 'name': 'Раздельный'},
        ],
    ),
    (
        BuildingMaterial,
        [
            {'code': 'brick', 'name': 'Кирпич'},
            {'code': 'panel', 'name': 'Панель'},
            {'code': 'monolith', 'name': 'Монолит'},
            {'code': 'block', 'name': 'Блок'},
            {'code': 'wood', 'name': 'Дерево'},
        ],
    ),
    (
        CommercialPropertyType,
        [
            {'code': 'office', 'name': 'Офис'},
            {'code': 'retail', 'name': 'Торговое помещение'},
            {'code': 'warehouse', 'name': 'Склад'},
            {'code': 'industrial', 'name': 'Производственное помещение'},
            {'code': 'free_purpose', 'name': 'Свободное назначение'},
            {'code': 'business', 'name': 'Бизнес'},
            {'code': 'commercial_land', 'name': 'Коммерческий участок'},
        ],
    ),
    (
        Amenity,
        [
            {'code': 'internet', 'name': 'Интернет'},
            {'code': 'air_conditioner', 'name': 'Кондиционер'},
            {'code': 'tv', 'name': 'Телевизор'},
            {'code': 'refrigerator', 'name': 'Холодильник'},
            {'code': 'washing_machine', 'name': 'Стиральная машина'},
            {'code': 'dishwasher', 'name': 'Посудомоечная машина'},
            {'code': 'security', 'name': 'Охрана'},
            {'code': 'intercom', 'name': 'Домофон'},
            {'code': 'furniture', 'name': 'Мебель'},
            {'code': 'parking', 'name': 'Парковка'},
        ],
    ),
    (
        AuditEntityType,
        [
            {'code': 'property', 'name': 'Объект недвижимости'},
            {'code': 'request', 'name': 'Заявка'},
            {'code': 'task', 'name': 'Задача'},
            {'code': 'deal', 'name': 'Сделка'},
            {'code': 'user', 'name': 'Пользователь'},
        ],
    ),
    (
        AuditAction,
        [
            {'code': 'created', 'name': 'Создан'},
            {'code': 'updated', 'name': 'Обновлен'},
            {'code': 'deleted', 'name': 'Удален'},
            {'code': 'status_changed', 'name': 'Статус изменен'},
            {'code': 'assigned', 'name': 'Назначен'},
            {'code': 'completed', 'name': 'Завершен'},
        ],
    ),
    (
        RequestMatchStatus,
        [
            {'code': 'proposed', 'name': 'Предложен'},
            {'code': 'viewed', 'name': 'Просмотрен'},
            {'code': 'approved', 'name': 'Одобрен клиентом'},
            {'code': 'rejected', 'name': 'Отклонен клиентом'},
            {'code': 'withdrawn', 'name': 'Снят с рассмотрения'},
        ],
    ),
    (
        DocumentType,
        [
            {'code': 'service_contract', 'name': 'Договор оказания услуг'},
            {'code': 'sale_contract', 'name': 'Договор купли-продажи'},
            {'code': 'rent_contract', 'name': 'Договор аренды'},
            {'code': 'acceptance_act', 'name': 'Акт приема-передачи'},
            {'code': 'agency_contract', 'name': 'Агентский договор'},
            {'code': 'power_of_attorney', 'name': 'Доверенность'},
            {'code': 'receipt', 'name': 'Расписка'},
            {'code': 'additional_agreement', 'name': 'Дополнительное соглашение'},
        ],
    ),
    (
        DealParticipantRole,
        [
            {'code': 'buyer', 'name': 'Покупатель'},
            {'code': 'seller', 'name': 'Продавец'},
            {'code': 'tenant', 'name': 'Арендатор'},
            {'code': 'landlord', 'name': 'Арендодатель'},
            {'code': 'guarantor', 'name': 'Поручитель'},
            {'code': 'co_borrower', 'name': 'Созаемщик'},
            {'code': 'representative', 'name': 'Представитель'},
            {'code': 'heir', 'name': 'Наследник'},
            {'code': 'trustee', 'name': 'Доверенное лицо'},
            {'code': 'other', 'name': 'Другое'},
        ],
    ),
    (
        ViewingStatus,
        [
            {'code': 'scheduled', 'name': 'Запланирован'},
            {'code': 'confirmed', 'name': 'Подтвержден'},
            {'code': 'in_progress', 'name': 'Идет просмотр'},
            {'code': 'completed', 'name': 'Завершен'},
            {'code': 'cancelled', 'name': 'Отменен'},
            {'code': 'no_show', 'name': 'Клиент не пришел'},
        ],
    ),
]

EMPLOYEE_SPECS = [
    ('admin', 'Анна', 'Соколова', 'Руководитель платформы'),
    ('admin', 'Илья', 'Морозов', 'Старший администратор'),
    ('manager', 'Марина', 'Орлова', 'Менеджер отдела продаж'),
    ('manager', 'Дмитрий', 'Жуков', 'Менеджер по развитию'),
    ('agent', 'Елена', 'Крылова', 'Агент по недвижимости'),
    ('agent', 'Павел', 'Смирнов', 'Агент по недвижимости'),
    ('agent', 'Наталья', 'Зорина', 'Агент по недвижимости'),
    ('agent', 'Роман', 'Белов', 'Агент по недвижимости'),
    ('agent', 'Ольга', 'Сергеева', 'Агент по недвижимости'),
    ('agent', 'Максим', 'Фомин', 'Агент по недвижимости'),
    ('agent', 'Алёна', 'Громова', 'Агент по недвижимости'),
    ('agent', 'Кирилл', 'Лапин', 'Агент по недвижимости'),
]

INDIVIDUAL_CLIENTS = [
    ('Алексей', 'Власов'),
    ('Юлия', 'Тарасова'),
    ('Сергей', 'Егоров'),
    ('Виктория', 'Романова'),
    ('Андрей', 'Матвеев'),
    ('Полина', 'Федорова'),
    ('Игорь', 'Кузнецов'),
    ('Татьяна', 'Соболева'),
    ('Никита', 'Савельев'),
    ('Дарья', 'Мельникова'),
]

COMPANY_CLIENTS = [
    'ООО Байкал Инвест',
    'ООО Столица Девелопмент',
    'ООО Амур Логистик',
    'ООО Восток Ритейл',
    'ООО Сибирский Парк',
]

PROPERTY_BLUEPRINTS = [
    ('irkutsk', 'apartment', 'studio', 0, '29.4', 6, 17, None, None, 'sale', 'active'),
    ('moscow', 'apartment', 'studio', 0, '31.2', 8, 24, None, None, 'rent', 'active'),
    ('irkutsk', 'apartment', 'one_room', 1, '37.8', 4, 10, None, None, 'sale', 'active'),
    ('moscow', 'apartment', 'one_room', 1, '41.6', 12, 22, None, None, 'sale', 'active'),
    ('khabarovsk', 'apartment', 'one_room', 1, '39.1', 5, 16, None, None, 'rent', 'active'),
    ('irkutsk', 'apartment', 'two_room', 2, '54.3', 7, 14, None, None, 'sale', 'active'),
    ('moscow', 'apartment', 'two_room', 2, '58.7', 9, 20, None, None, 'sale', 'reserved'),
    ('khabarovsk', 'apartment', 'two_room', 2, '56.8', 11, 19, None, None, 'sale', 'active'),
    ('chita', 'apartment', 'two_room', 2, '52.4', 3, 9, None, None, 'rent', 'pending'),
    ('irkutsk', 'apartment', 'three_room', 3, '76.5', 10, 16, None, None, 'sale', 'active'),
    ('moscow', 'apartment', 'three_room', 3, '82.9', 15, 28, None, None, 'sale', 'active'),
    ('khabarovsk', 'apartment', 'three_room', 3, '74.1', 4, 12, None, None, 'sale', 'reserved'),
    ('irkutsk', 'apartment', 'four_room', 4, '96.8', 12, 18, None, None, 'rent', 'active'),
    ('moscow', 'apartment', 'four_room', 4, '108.5', 19, 30, None, None, 'sale', 'active'),
    ('irkutsk', 'house', 'private_house', 4, '138.0', 1, 2, '920.0', None, 'sale', 'active'),
    ('moscow', 'house', 'private_house', 5, '164.0', 1, 2, '1150.0', None, 'rent', 'active'),
    ('irkutsk', 'house', 'townhouse', 4, '126.5', 2, 3, '280.0', None, 'sale', 'reserved'),
    ('moscow', 'house', 'townhouse', 4, '132.4', 1, 3, '310.0', None, 'sale', 'active'),
    ('khabarovsk', 'house', 'duplex', 5, '154.7', 2, 2, '640.0', None, 'sale', 'pending'),
    ('chita', 'room', 'communal_room', 1, '18.7', 3, 5, None, None, 'sale', 'active'),
    ('khabarovsk', 'room', 'dorm_room', 1, '20.9', 5, 9, None, None, 'rent', 'active'),
    ('irkutsk', 'room', 'dorm_room', 1, '22.3', 4, 8, None, None, 'rent', 'active'),
    ('moscow', 'commercial', 'office', None, '72.0', 5, 11, None, 'office', 'rent', 'active'),
    ('irkutsk', 'commercial', 'office', None, '118.0', 3, 7, None, 'office', 'sale', 'pending'),
    ('moscow', 'commercial', 'retail', None, '96.0', 1, 14, None, 'retail', 'rent', 'reserved'),
    ('khabarovsk', 'commercial', 'retail', None, '164.0', 1, 9, None, 'retail', 'sale', 'active'),
    ('chita', 'commercial', 'warehouse', None, '420.0', 1, 2, None, 'warehouse', 'sale', 'sold'),
    ('irkutsk', 'land', 'ijs_land', None, '1000.0', None, 1, '1000.0', None, 'sale', 'active'),
    ('moscow', 'land', 'commercial_land', None, '2100.0', None, 1, '2100.0', None, 'sale', 'archived'),
    ('chita', 'garage', 'gsk_garage', None, '24.5', 1, 1, None, None, 'rent', 'rented'),
]
