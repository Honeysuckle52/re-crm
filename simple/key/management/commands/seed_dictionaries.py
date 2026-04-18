"""
Management-команда заполнения справочников учётной системы недвижимости.

Использование::

    python manage.py seed_dictionaries
    python manage.py seed_dictionaries --flush   # предварительно очистить

Команда идемпотентна: повторный запуск не создаёт дублей — используется
``update_or_create`` по уникальному полю ``code`` / ``name``.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import (
    OperationType,
    PropertyStatus,
    RequestStatus,
    DealStatus,
    TaskStatus,
    UserRole,
    PropertyFeature,
)


OPERATION_TYPES = [
    {"code": "sale", "name": "Продажа"},
    {"code": "rent", "name": "Аренда"},
]

PROPERTY_STATUSES = [
    {"code": "active",   "name": "Активно"},
    {"code": "reserved", "name": "Зарезервировано"},
    {"code": "sold",     "name": "Продано"},
    {"code": "rented",   "name": "Сдано"},
    {"code": "archived", "name": "В архиве"},
]

REQUEST_STATUSES = [
    {"code": "open",       "name": "Открыта"},
    {"code": "processing", "name": "В обработке"},
    {"code": "closed",     "name": "Закрыта"},
    {"code": "cancelled",  "name": "Отменена"},
]

DEAL_STATUSES = [
    {"code": "new",         "name": "Новая",             "order": 10},
    {"code": "negotiation", "name": "Переговоры",        "order": 20},
    {"code": "documents",   "name": "Подготовка документов", "order": 30},
    {"code": "signed",      "name": "Договор подписан",  "order": 40},
    {"code": "completed",   "name": "Завершена",         "order": 50},
    {"code": "cancelled",   "name": "Отменена",          "order": 90},
]

TASK_STATUSES = [
    {"code": "new",         "name": "Новая",       "order": 10},
    {"code": "in_progress", "name": "В работе",    "order": 20},
    {"code": "waiting",     "name": "Ожидание",    "order": 30},
    {"code": "done",        "name": "Выполнена",   "order": 40},
    {"code": "cancelled",   "name": "Отменена",    "order": 90},
]

USER_ROLES = [
    {"code": "admin",   "name": "Администратор",
     "description": "Полный доступ ко всем функциям системы"},
    {"code": "manager", "name": "Менеджер",
     "description": "Управление сотрудниками, объектами и сделками"},
    {"code": "agent",   "name": "Агент",
     "description": "Работа с клиентами, объектами и заявками"},
]

PROPERTY_FEATURES = [
    {"name": "Балкон",       "category": "Комфорт"},
    {"name": "Лоджия",       "category": "Комфорт"},
    {"name": "Свежий ремонт", "category": "Состояние"},
    {"name": "Требует ремонта", "category": "Состояние"},
    {"name": "Парковка",     "category": "Инфраструктура"},
    {"name": "Лифт",         "category": "Инфраструктура"},
    {"name": "Мебель",       "category": "Комфорт"},
    {"name": "Бытовая техника", "category": "Комфорт"},
    {"name": "Интернет",     "category": "Коммуникации"},
    {"name": "Кондиционер",  "category": "Комфорт"},
    {"name": "Охрана",       "category": "Безопасность"},
    {"name": "Видеонаблюдение", "category": "Безопасность"},
]


class Command(BaseCommand):
    help = "Заполняет справочники системы (типы, статусы, роли, характеристики)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Очистить справочники перед заполнением.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write(self.style.WARNING("Очистка справочников..."))
            PropertyFeature.objects.all().delete()
            UserRole.objects.all().delete()
            TaskStatus.objects.all().delete()
            DealStatus.objects.all().delete()
            RequestStatus.objects.all().delete()
            PropertyStatus.objects.all().delete()
            OperationType.objects.all().delete()

        created_counts = {
            "Типы операций":       self._seed(OperationType,   OPERATION_TYPES,   key="code"),
            "Статусы объектов":    self._seed(PropertyStatus,  PROPERTY_STATUSES, key="code"),
            "Статусы заявок":      self._seed(RequestStatus,   REQUEST_STATUSES,  key="code"),
            "Статусы сделок":      self._seed(DealStatus,      DEAL_STATUSES,     key="code"),
            "Статусы задач":       self._seed(TaskStatus,      TASK_STATUSES,     key="code"),
            "Роли пользователей":  self._seed(UserRole,        USER_ROLES,        key="code"),
            "Характеристики":      self._seed(PropertyFeature, PROPERTY_FEATURES, key="name"),
        }

        self.stdout.write(self.style.SUCCESS("Справочники успешно заполнены:"))
        for title, (created, updated) in created_counts.items():
            self.stdout.write(
                f"  {title:>22}: создано {created}, обновлено {updated}"
            )

    @staticmethod
    def _seed(model, rows, key):
        """Создаёт или обновляет записи. Возвращает (created, updated)."""
        created, updated = 0, 0
        for row in rows:
            lookup = {key: row[key]}
            defaults = {k: v for k, v in row.items() if k != key}
            _, was_created = model.objects.update_or_create(
                defaults=defaults, **lookup
            )
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated
