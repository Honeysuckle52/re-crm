"""
Management-команда заполнения справочников CRM/ERP недвижимости.

Использование:
    python manage.py seed_dictionaries
    python manage.py seed_dictionaries --flush   # предварительно очистить справочники

Команда идемпотентна: повторный запуск не создаёт дублей
(используется update_or_create по уникальному полю `code` / `name`).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import (
    OperationType,
    PropertyStatus,
    RequestStatus,
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
]

REQUEST_STATUSES = [
    {"code": "open",       "name": "Открыта"},
    {"code": "processing", "name": "В обработке"},
    {"code": "closed",     "name": "Закрыта"},
]

USER_ROLES = [
    {"code": "admin",   "name": "Администратор",
     "description": "Полный доступ ко всем функциям системы"},
    {"code": "manager", "name": "Менеджер",
     "description": "Управление сделками и сотрудниками"},
    {"code": "agent",   "name": "Агент",
     "description": "Работа с клиентами и объектами"},
]

PROPERTY_FEATURES = [
    {"name": "Балкон",   "category": "Комфорт"},
    {"name": "Лоджия",   "category": "Комфорт"},
    {"name": "Ремонт",   "category": "Состояние"},
    {"name": "Парковка", "category": "Инфраструктура"},
    {"name": "Лифт",     "category": "Инфраструктура"},
    {"name": "Мебель",   "category": "Комфорт"},
    {"name": "Техника",  "category": "Комфорт"},
    {"name": "Интернет", "category": "Коммуникации"},
]


class Command(BaseCommand):
    help = "Заполняет справочники (типы операций, статусы, роли, характеристики)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Предварительно очистить справочники перед заполнением.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write(self.style.WARNING("Очистка справочников..."))
            PropertyFeature.objects.all().delete()
            UserRole.objects.all().delete()
            RequestStatus.objects.all().delete()
            PropertyStatus.objects.all().delete()
            OperationType.objects.all().delete()

        created_counts = {
            "OperationType":    self._seed(OperationType,   OPERATION_TYPES,   key="code"),
            "PropertyStatus":   self._seed(PropertyStatus,  PROPERTY_STATUSES, key="code"),
            "RequestStatus":    self._seed(RequestStatus,   REQUEST_STATUSES,  key="code"),
            "UserRole":         self._seed(UserRole,        USER_ROLES,        key="code"),
            "PropertyFeature":  self._seed(PropertyFeature, PROPERTY_FEATURES, key="name"),
        }

        self.stdout.write(self.style.SUCCESS("Справочники успешно заполнены:"))
        for model_name, (created, updated) in created_counts.items():
            self.stdout.write(
                f"  {model_name:>18}: создано {created}, обновлено {updated}"
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
