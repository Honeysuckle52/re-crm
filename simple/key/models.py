# -*- coding: utf-8 -*-
"""ORM-модели приложения ``key`` (3NF-версия)."""
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.utils import timezone

from .storage import database_backup_storage

# Поле ``Task.property`` перекрывает builtins.property.
_property = property

phone_validator = RegexValidator(
    regex=r'^\+7\d{10}$',
    message='Телефон должен быть российским номером в формате +7XXXXXXXXXX.',
)
passport_series_validator = RegexValidator(
    regex=r'^\d{4}$',
    message='Серия паспорта должна состоять из 4 цифр.',
)
passport_number_validator = RegexValidator(
    regex=r'^\d{6}$',
    message='Номер паспорта должен состоять из 6 цифр.',
)
passport_code_validator = RegexValidator(
    regex=r'^\d{3}-\d{3}$',
    message='Код подразделения должен быть в формате 000-000.',
)
company_inn_validator = RegexValidator(
    regex=r'^\d{10}$',
    message='ИНН юридического лица должен состоять из 10 цифр.',
)
company_ogrn_validator = RegexValidator(
    regex=r'^\d{13}$',
    message='ОГРН должен состоять из 13 цифр.',
)
company_kpp_validator = RegexValidator(
    regex=r'^\d{9}$',
    message='КПП должен состоять из 9 цифр.',
)
cadastral_number_validator = RegexValidator(
    regex=r'^\d{2}:\d{2}:\d{6,}:\d+$',
    message='Неверный формат кадастрового номера.',
)


# =====================================================
# 1. БАЗОВЫЕ КЛАССЫ И УТИЛИТЫ
# =====================================================

LOOKUP_NAME_DEFAULTS = {
    'PropertyType': {
        'apartment': 'Квартира',
        'house': 'Дом',
        'commercial': 'Коммерческая недвижимость',
        'land': 'Земельный участок',
        'garage': 'Гараж',
        'room': 'Комната',
    },
    'TaskPriority': {
        'low': 'Низкий',
        'normal': 'Обычный',
        'high': 'Высокий',
    },
    'TaskType': {
        'contact_client': 'Связаться с клиентом',
        'property_search': 'Подбор объектов',
        'showing': 'Показ объекта',
        'documents': 'Подготовка документов',
        'call': 'Звонок',
        'other': 'Прочее',
    },
    'ClientKind': {
        'individual': 'Физическое лицо',
        'company': 'Юридическое лицо',
    },
    'ContactMethod': {
        'phone': 'Телефон',
        'email': 'Email',
        'telegram': 'Telegram',
        'whatsapp': 'WhatsApp',
    },
    'ContractStatus': {
        'not_requested': 'Не запрошен',
        'pending': 'В очереди',
        'processing': 'Формируется',
        'ready': 'Готов',
        'failed': 'Ошибка',
    },
    'UserType': {
        'employee': 'Сотрудник',
        'client': 'Клиент',
    },
}

LOOKUP_DEFAULT_CODES = {
    'UserType': 'client',
    'ClientKind': 'individual',
    'ContractStatus': 'not_requested',
    'PropertyStatus': 'active',
    'PropertyType': 'apartment',
    'RequestStatus': 'open',
    'RequestMatchStatus': 'proposed',
    'ViewingStatus': 'scheduled',
    'TaskPriority': 'normal',
    'TaskType': 'other',
}


def _lookup_default_name(model_class, code: str) -> str:
    return LOOKUP_NAME_DEFAULTS.get(model_class.__name__, {}).get(code, code)


def _lookup_default_code(model_class) -> str | None:
    return LOOKUP_DEFAULT_CODES.get(model_class.__name__)


def _lookup_choices(model_name: str, codes: tuple[str, ...]) -> list[tuple[str, str]]:
    defaults = LOOKUP_NAME_DEFAULTS.get(model_name, {})
    return [(code, defaults.get(code, code)) for code in codes]


def _resolve_lookup_instance(model_class, value):
    if value in (None, ''):
        return None
    if isinstance(value, model_class):
        return value
    if isinstance(value, int):
        return model_class.objects.filter(pk=value).first()
    code = str(value).strip()
    if not code:
        return None
    instance = model_class.objects.filter(code=code).first()
    if instance is not None:
        return instance
    return model_class.objects.create(
        code=code,
        name=_lookup_default_name(model_class, code),
    )


def _ensure_lookup_default(instance, field_name: str, model_class) -> None:
    if getattr(instance, f'{field_name}_id', None):
        return
    default_code = _lookup_default_code(model_class)
    if not default_code:
        return
    setattr(instance, field_name, _resolve_lookup_instance(model_class, default_code))


def _resolve_user_profile(value, profile_attr: str):
    """Нормализует пользователя или id к связанному профилю."""
    if value in (None, ''):
        return None

    profile_model_name = 'ClientProfile' if profile_attr == 'client_profile' else 'EmployeeProfile'
    profile_model = globals().get(profile_model_name)

    def _profile_defaults(user):
        username = (getattr(user, 'username', '') or '').strip() or 'user'
        first_name = username.split('.')[0].split('_')[0].split('-')[0] or username
        return {
            'first_name': first_name[:50],
            'last_name': username[:50],
        }

    def _ensure_profile(user):
        if user is None:
            return None
        try:
            return getattr(user, profile_attr)
        except Exception:
            pass
        if profile_model is None:
            return None
        if profile_attr == 'client_profile' and getattr(user, 'user_type', None) == 'client':
            defaults = _profile_defaults(user)
            defaults['client_kind'] = ClientProfile.CLIENT_KIND_INDIVIDUAL
            return profile_model.objects.create(user=user, **defaults)
        if profile_attr == 'employee_profile' and getattr(user, 'user_type', None) == 'employee':
            return profile_model.objects.create(user=user, **_profile_defaults(user))
        return None

    if profile_model is not None and isinstance(value, profile_model):
        return value

    if isinstance(value, User):
        return _ensure_profile(value)

    if hasattr(value, profile_attr):
        try:
            profile = getattr(value, profile_attr)
        except Exception:
            profile = None
        if profile is not None:
            return profile

    try:
        user_id = int(getattr(value, 'pk', value))
    except (TypeError, ValueError):
        return None

    user = User.objects.select_related(profile_attr).filter(pk=user_id).first()
    if user is None:
        return None
    return _ensure_profile(user)


def _rewrite_legacy_update_fields(instance, kwargs):
    update_fields = kwargs.get('update_fields')
    if not update_fields:
        return

    alias_map = getattr(instance, 'QUERY_ALIASES', {})
    concrete_names = {field.name for field in instance._meta.concrete_fields}
    concrete_names.update(field.attname for field in instance._meta.concrete_fields)

    rewritten = []
    for field_name in update_fields:
        if field_name in concrete_names:
            rewritten.append(field_name)
            continue
        target = alias_map.get(field_name, field_name)
        concrete_name = target.split('__', 1)[0]
        rewritten.append(concrete_name if concrete_name in concrete_names else field_name)

    kwargs['update_fields'] = list(dict.fromkeys(rewritten))


class CodeNameLookup(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name='Код')
    name = models.CharField(max_length=100, verbose_name='Название')

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.code == other
        return super().__eq__(other)

    def __hash__(self):
        return hash((self.__class__, self.pk, self.code))


class AliasQuerySet(models.QuerySet):
    def _alias_map(self):
        return getattr(self.model, 'QUERY_ALIASES', {})

    def _rewrite_key(self, key: str) -> str:
        alias_map = self._alias_map()
        for alias, target in sorted(alias_map.items(), key=lambda item: len(item[0]), reverse=True):
            if key == alias:
                return target
            if key.startswith(f'{alias}__'):
                return f'{target}{key[len(alias):]}'
        return key

    def _rewrite_q(self, node):
        if not isinstance(node, models.Q):
            return node
        rewritten_children = []
        for child in node.children:
            if isinstance(child, tuple):
                key, value = child
                rewritten_children.append((self._rewrite_key(key), value))
            else:
                rewritten_children.append(self._rewrite_q(child))
        clone = models.Q()
        clone.connector = node.connector
        clone.negated = node.negated
        clone.children = rewritten_children
        return clone

    def _rewrite_kwargs(self, kwargs):
        return {self._rewrite_key(key): value for key, value in kwargs.items()}

    def _rewrite_update_kwargs(self, kwargs):
        rewritten = {}
        alias_map = self._alias_map()
        for key, value in kwargs.items():
            target = alias_map.get(key)
            if target is None:
                rewritten[key] = value
                continue

            if '__' not in target:
                rewritten[target] = value
                continue

            field_name, lookup = target.split('__', 1)
            try:
                field = self.model._meta.get_field(field_name)
            except Exception:
                rewritten[field_name] = value
                continue

            if lookup == 'code' and getattr(field, 'remote_field', None):
                related_model = field.remote_field.model
                resolved = _resolve_lookup_instance(related_model, value)
                rewritten[field.attname] = getattr(resolved, 'pk', None)
                continue

            rewritten[field_name] = value
        return rewritten

    def filter(self, *args, **kwargs):
        rewritten_args = tuple(self._rewrite_q(arg) for arg in args)
        return super().filter(*rewritten_args, **self._rewrite_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        rewritten_args = tuple(self._rewrite_q(arg) for arg in args)
        return super().exclude(*rewritten_args, **self._rewrite_kwargs(kwargs))

    def get(self, *args, **kwargs):
        rewritten_args = tuple(self._rewrite_q(arg) for arg in args)
        return super().get(*rewritten_args, **self._rewrite_kwargs(kwargs))

    def order_by(self, *field_names):
        rewritten = []
        for field_name in field_names:
            prefix = '-' if field_name.startswith('-') else ''
            raw = field_name[1:] if prefix else field_name
            rewritten.append(prefix + self._rewrite_key(raw))
        return super().order_by(*rewritten)

    def select_related(self, *fields):
        return super().select_related(*(self._rewrite_key(field) for field in fields))

    def update(self, **kwargs):
        alias_map = self._alias_map()
        direct_kwargs = {}
        row_level_updates = []

        for key, value in kwargs.items():
            target = alias_map.get(key)
            if target is None:
                direct_kwargs[key] = value
                continue

            if '__' not in target:
                direct_kwargs[target] = value
                continue

            field_name, lookup = target.split('__', 1)
            try:
                field = self.model._meta.get_field(field_name)
            except Exception:
                direct_kwargs[field_name] = value
                continue

            if lookup == 'code' and getattr(field, 'remote_field', None):
                related_model = field.remote_field.model
                resolved = _resolve_lookup_instance(related_model, value)
                direct_kwargs[field.attname] = getattr(resolved, 'pk', None)
                continue

            row_level_updates.append((key, value))

        affected = self.count()
        if direct_kwargs:
            super().update(**direct_kwargs)
        if row_level_updates:
            for obj in self:
                for key, value in row_level_updates:
                    setattr(obj, key, value)
                obj.save()
        return affected


class AliasManager(models.Manager):
    def get_queryset(self):
        return AliasQuerySet(self.model, using=self._db, hints=self._hints)


# =====================================================
# 2. СПРАВОЧНИКИ (LOOKUPS)
# =====================================================

class OperationType(models.Model):
    """Тип операции с недвижимостью (продажа / аренда)."""
    code = models.CharField(max_length=10, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')

    class Meta:
        db_table = 'operation_types'
        verbose_name = 'Тип операции'
        verbose_name_plural = 'Типы операций'

    def __str__(self):
        return self.name


class PropertyStatus(models.Model):
    """Статус объекта недвижимости."""
    code = models.CharField(max_length=10, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')

    class Meta:
        db_table = 'property_statuses'
        verbose_name = 'Статус объекта'
        verbose_name_plural = 'Статусы объектов'

    def __str__(self):
        return self.name


class RequestStatus(models.Model):
    """Статус заявки клиента."""
    code = models.CharField(max_length=15, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')

    class Meta:
        db_table = 'request_statuses'
        verbose_name = 'Статус заявки'
        verbose_name_plural = 'Статусы заявок'

    def __str__(self):
        return self.name


class DealStatus(models.Model):
    """Статус сделки — стадия воронки продаж."""
    code = models.CharField(max_length=20, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')
    order = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)], verbose_name='Порядок')

    class Meta:
        db_table = 'deal_statuses'
        verbose_name = 'Статус сделки'
        verbose_name_plural = 'Статусы сделок'
        ordering = ['order']

    def __str__(self):
        return self.name


class TaskStatus(models.Model):
    """Статус задачи сотрудника."""
    code = models.CharField(max_length=20, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')
    order = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)], verbose_name='Порядок')

    class Meta:
        db_table = 'task_statuses'
        verbose_name = 'Статус задачи'
        verbose_name_plural = 'Статусы задач'
        ordering = ['order']

    def __str__(self):
        return self.name


class PropertyType(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'property_types'
        verbose_name = 'Тип помещения'
        verbose_name_plural = 'Типы помещений'


class TaskPriority(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'task_priorities'
        verbose_name = 'Приоритет задачи'
        verbose_name_plural = 'Приоритеты задач'


class TaskType(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'task_types'
        verbose_name = 'Тип задачи'
        verbose_name_plural = 'Типы задач'


class ClientKind(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'client_kinds'
        verbose_name = 'Вид клиента'
        verbose_name_plural = 'Виды клиентов'


class ContactMethod(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'contact_methods'
        verbose_name = 'Способ связи'
        verbose_name_plural = 'Способы связи'


class ContractStatus(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'contract_statuses'
        verbose_name = 'Статус договора'
        verbose_name_plural = 'Статусы договоров'


class UserType(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'user_types'
        verbose_name = 'Тип пользователя'
        verbose_name_plural = 'Типы пользователей'


class RenovationType(CodeNameLookup):
    """Тип ремонта."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'renovation_types'
        verbose_name = 'Тип ремонта'
        verbose_name_plural = 'Типы ремонтов'


class BathroomType(CodeNameLookup):
    """Тип санузла (совмещённый/раздельный)."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'bathroom_types'
        verbose_name = 'Тип санузла'
        verbose_name_plural = 'Типы санузлов'


class BuildingMaterial(CodeNameLookup):
    """Материал стен."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'building_materials'
        verbose_name = 'Материал стен'
        verbose_name_plural = 'Материалы стен'


class CommercialPropertyType(CodeNameLookup):
    """Тип коммерческой недвижимости."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'commercial_property_types'
        verbose_name = 'Тип коммерческой недвижимости'
        verbose_name_plural = 'Типы коммерческой недвижимости'


class Amenity(CodeNameLookup):
    """Удобства/особенности объекта."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'amenities'
        verbose_name = 'Удобство'
        verbose_name_plural = 'Удобства'


class AuditEntityType(CodeNameLookup):
    """Тип сущности для аудита."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'audit_entity_types'
        verbose_name = 'Тип сущности аудита'
        verbose_name_plural = 'Типы сущностей аудита'


class AuditAction(CodeNameLookup):
    """Действие для аудита."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'audit_actions'
        verbose_name = 'Действие аудита'
        verbose_name_plural = 'Действия аудита'


class RequestMatchStatus(CodeNameLookup):
    """Статус соответствия заявка-объект."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'request_match_statuses'
        verbose_name = 'Статус соответствия'
        verbose_name_plural = 'Статусы соответствий'


class DocumentType(CodeNameLookup):
    """Тип документа."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'document_types'
        verbose_name = 'Тип документа'
        verbose_name_plural = 'Типы документов'


class DealParticipantRole(CodeNameLookup):
    """Роль участника сделки."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'deal_participant_roles'
        verbose_name = 'Роль участника сделки'
        verbose_name_plural = 'Роли участников сделок'


class ViewingStatus(CodeNameLookup):
    """Статус просмотра объекта."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'viewing_statuses'
        verbose_name = 'Статус просмотра'
        verbose_name_plural = 'Статусы просмотров'


class UserRole(models.Model):
    """Роль сотрудника в системе (администратор / менеджер / агент)."""
    DEFAULT_MAX_ACTIVE_TASKS = 2
    DEFAULT_MAX_IN_PROGRESS_TASKS = 1
    DEFAULT_MAX_ACTIVE_REQUESTS = 2

    code = models.CharField(max_length=20, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    def __init__(self, *args, **kwargs):
        self._max_active_tasks = self._coerce_limit(
            kwargs.pop('max_active_tasks', self.DEFAULT_MAX_ACTIVE_TASKS),
            self.DEFAULT_MAX_ACTIVE_TASKS,
        )
        self._max_in_progress_tasks = self._coerce_limit(
            kwargs.pop('max_in_progress_tasks', self.DEFAULT_MAX_IN_PROGRESS_TASKS),
            self.DEFAULT_MAX_IN_PROGRESS_TASKS,
        )
        self._max_active_requests = self._coerce_limit(
            kwargs.pop('max_active_requests', self.DEFAULT_MAX_ACTIVE_REQUESTS),
            self.DEFAULT_MAX_ACTIVE_REQUESTS,
        )
        super().__init__(*args, **kwargs)

    class Meta:
        db_table = 'user_roles'
        verbose_name = 'Роль пользователя'
        verbose_name_plural = 'Роли пользователей'

    def __str__(self):
        return self.name

    @staticmethod
    def _coerce_limit(value, default):
        if value in (None, ''):
            return default
        try:
            result = int(value)
        except (TypeError, ValueError):
            return default
        return result if result >= 1 else default

    @property
    def max_active_tasks(self):
        return self._max_active_tasks

    @max_active_tasks.setter
    def max_active_tasks(self, value):
        self._max_active_tasks = self._coerce_limit(value, self.DEFAULT_MAX_ACTIVE_TASKS)

    @property
    def max_in_progress_tasks(self):
        return self._max_in_progress_tasks

    @max_in_progress_tasks.setter
    def max_in_progress_tasks(self, value):
        self._max_in_progress_tasks = self._coerce_limit(
            value,
            self.DEFAULT_MAX_IN_PROGRESS_TASKS,
        )

    @property
    def max_active_requests(self):
        return self._max_active_requests

    @max_active_requests.setter
    def max_active_requests(self, value):
        self._max_active_requests = self._coerce_limit(
            value,
            self.DEFAULT_MAX_ACTIVE_REQUESTS,
        )


# =====================================================
# 3. АДРЕСА
# =====================================================

class City(models.Model):
    """Город / населённый пункт."""
    name = models.CharField(max_length=100, verbose_name='Название')
    region = models.CharField(max_length=100, blank=True, null=True, verbose_name='Регион')
    external_id = models.UUIDField(
        blank=True, null=True, db_index=True,
        help_text='Внешний идентификатор адресного реестра (из DaData)',
        verbose_name='Внешний идентификатор',
    )

    class Meta:
        db_table = 'cities'
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        indexes = [models.Index(fields=['name'])]
        unique_together = [['name', 'region']]

    def __str__(self):
        return f'{self.name}, {self.region}' if self.region else self.name


class Street(models.Model):
    """Улица."""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='streets', verbose_name='Город')
    name = models.CharField(max_length=150, verbose_name='Название')
    street_type = models.CharField(max_length=20, blank=True, null=True, verbose_name='Тип улицы')
    external_id = models.UUIDField(blank=True, null=True, db_index=True, verbose_name='Внешний идентификатор')

    class Meta:
        db_table = 'streets'
        verbose_name = 'Улица'
        verbose_name_plural = 'Улицы'
        unique_together = [['city', 'name']]

    def __str__(self):
        return f'{self.street_type or ""} {self.name}'.strip()


class House(models.Model):
    """Дом / строение."""
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='houses', verbose_name='Улица')
    house_number = models.CharField(max_length=20, verbose_name='Номер дома')
    postal_code = models.CharField(max_length=10, blank=True, null=True, verbose_name='Почтовый индекс')
    external_id = models.UUIDField(blank=True, null=True, db_index=True, verbose_name='Внешний идентификатор')

    class Meta:
        db_table = 'houses'
        verbose_name = 'Дом'
        verbose_name_plural = 'Дома'
        unique_together = [['street', 'house_number']]

    def __str__(self):
        return f'{self.street.city}, {self.street}, д. {self.house_number}'

    @property
    def house(self):
        return self


class AddressCompatibilityManager:
    """Совместимость со старым API Address после удаления сущности."""

    model = House

    @staticmethod
    def _rewrite_key(key: str) -> str:
        if key == 'house':
            return 'pk'
        if key.startswith('house__'):
            return key[len('house__'):]
        return key

    def _rewrite_kwargs(self, kwargs):
        rewritten = {}
        for key, value in kwargs.items():
            target_key = self._rewrite_key(key)
            if target_key == 'pk' and isinstance(value, House):
                rewritten[target_key] = value.pk
            else:
                rewritten[target_key] = value
        return rewritten

    def get_queryset(self):
        return House.objects.all()

    def all(self):
        return self.get_queryset()

    def select_related(self, *fields):
        rewritten = []
        for field in fields:
            mapped = self._rewrite_key(field)
            if mapped:
                rewritten.append(mapped)
        return self.get_queryset().select_related(*rewritten)

    def filter(self, *args, **kwargs):
        return self.get_queryset().filter(*args, **self._rewrite_kwargs(kwargs))

    def get(self, *args, **kwargs):
        return self.get_queryset().get(*args, **self._rewrite_kwargs(kwargs))

    def create(self, **kwargs):
        house = kwargs.get('house')
        if isinstance(house, House):
            return house
        if house not in (None, ''):
            return self.get(pk=house)
        raise TypeError('Address compatibility layer requires house=House(...) or house=<id>.')

    def get_or_create(self, defaults=None, **kwargs):
        house = kwargs.get('house')
        if isinstance(house, House):
            return house, False
        if house not in (None, ''):
            return self.get(pk=house), False
        raise TypeError('Address compatibility layer requires house=House(...) or house=<id>.')


class Address:
    """Немигрируемая совместимость: старый Address теперь указывает на House."""

    objects = AddressCompatibilityManager()
    DoesNotExist = House.DoesNotExist
    MultipleObjectsReturned = House.MultipleObjectsReturned


# =====================================================
# 4. ПОЛЬЗОВАТЕЛИ И ПРОФИЛИ
# =====================================================

class UserManager(BaseUserManager):
    """Менеджер кастомной модели пользователя."""

    def get_queryset(self):
        return AliasQuerySet(self.model, using=self._db, hints=self._hints)

    def create_user(self, username, email, password=None, **extra):
        if not username:
            raise ValueError('Логин обязателен')
        if not email:
            raise ValueError('Электронная почта обязательна')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra):
        extra.setdefault('user_type', 'employee')
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('is_active', True)
        return self.create_user(username, email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Единая таблица сотрудников и клиентов."""
    USER_TYPE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('client', 'Клиент'),
    ]

    username = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Логин',
    )
    email = models.EmailField(max_length=255, unique=True, verbose_name='Email')
    phone = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        validators=[phone_validator],
        verbose_name='Телефон',
    )

    user_type_ref = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name='users',
        verbose_name='Тип пользователя',
        blank=True,
        null=True,
    )
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL,
                             verbose_name='Роль',
                             blank=True, null=True, related_name='users')

    is_active = models.BooleanField(default=True, verbose_name='Активен')
    is_staff = models.BooleanField(default=False, verbose_name='Сотрудник')
    is_email_verified = models.BooleanField(default=False, verbose_name='Email подтвержден')
    is_phone_verified = models.BooleanField(default=False, verbose_name='Телефон подтвержден')

    last_login = models.DateTimeField(blank=True, null=True, verbose_name='Последний вход')

    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    QUERY_ALIASES = {
        'user_type': 'user_type_ref__code',
        'user_type_id': 'user_type_ref_id',
    }

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f'{self.username} ({self.get_user_type_display()})'

    def __init__(self, *args, **kwargs):
        legacy_user_type = kwargs.pop('user_type', None)
        has_user_type_ref = 'user_type_ref' in kwargs or 'user_type_ref_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_user_type not in (None, '') and not has_user_type_ref:
            self.user_type = legacy_user_type

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'user_type_ref', UserType)
        if self.email:
            self.email = User.objects.normalize_email(self.email)
        if self.phone == '':
            self.phone = None
        if self.user_type == 'client' and (self.is_staff or self.is_superuser):
            raise ValidationError({
                'user_type': 'Клиент не может иметь доступ к административной панели.',
                'is_staff': 'Для клиента доступ staff должен быть выключен.',
            })
        if self.user_type == 'client' and self.role_id:
            raise ValidationError({
                'role': 'Р оль назначается только сотрудникам.',
            })
        if self.is_staff and self.user_type != 'employee':
            raise ValidationError({
                'user_type': 'Доступ в админку разрешён только сотрудникам.',
            })

    @property
    def role_code(self) -> str | None:
        return self.role.code if self.role_id else None

    @property
    def user_type(self) -> str | None:
        return self.user_type_ref.code if self.user_type_ref_id else None

    @user_type.setter
    def user_type(self, value):
        self.user_type_ref = _resolve_lookup_instance(UserType, value)

    def get_user_type_display(self) -> str:
        if not self.user_type_ref_id:
            return ''
        return self.user_type_ref.name

    def save(self, *args, **kwargs):
        _ensure_lookup_default(self, 'user_type_ref', UserType)
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)

    @property
    def is_admin_role(self) -> bool:
        return self.is_superuser or self.role_code == 'admin'

    @property
    def is_manager_role(self) -> bool:
        return self.role_code in {'manager', 'moderator'}

    @property
    def is_moderator_role(self) -> bool:
        return self.role_code in {'manager', 'moderator'}

    @property
    def is_admin_or_manager(self) -> bool:
        return self.is_admin_role or self.is_moderator_role

    @property
    def is_employee(self) -> bool:
        return self.user_type == 'employee'

    @property
    def is_client(self) -> bool:
        return self.user_type == 'client'


class EmployeeProfile(models.Model):
    """Профиль сотрудника."""
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                verbose_name='Пользователь',
                                related_name='employee_profile')
    first_name = models.CharField(max_length=50, verbose_name='Имя')
    last_name = models.CharField(max_length=50, verbose_name='Фамилия')
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name='Должность')
    hire_date = models.DateField(blank=True, null=True, verbose_name='Дата найма')
    internal_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Внутренний телефон')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'employee_profiles'
        verbose_name = 'Профиль сотрудника'
        verbose_name_plural = 'Профили сотрудников'

    def __init__(self, *args, **kwargs):
        self._legacy_middle_name = kwargs.pop('middle_name', None)
        self._legacy_department = kwargs.pop('department', None)
        self._legacy_notes = kwargs.pop('notes', None)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    def clean(self):
        super().clean()
        if self.user_id and self.user.user_type != 'employee':
            raise ValidationError({'user': 'Профиль сотрудника можно привязать только к пользователю типа "Сотрудник".'})

    @property
    def middle_name(self):
        return self._legacy_middle_name

    @middle_name.setter
    def middle_name(self, value):
        self._legacy_middle_name = value

    @property
    def department(self):
        return self._legacy_department

    @department.setter
    def department(self, value):
        self._legacy_department = value

    @property
    def notes(self):
        return self._legacy_notes

    @notes.setter
    def notes(self, value):
        self._legacy_notes = value


class ClientProfile(models.Model):
    """Профиль клиента."""
    CLIENT_KIND_INDIVIDUAL = 'individual'
    CLIENT_KIND_COMPANY = 'company'
    CLIENT_KIND_CHOICES = _lookup_choices(
        'ClientKind',
        (CLIENT_KIND_INDIVIDUAL, CLIENT_KIND_COMPANY),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                verbose_name='Пользователь',
                                related_name='client_profile')
    first_name = models.CharField(max_length=50, verbose_name='Имя')
    last_name = models.CharField(max_length=50, verbose_name='Фамилия')
    middle_name = models.CharField(max_length=50, blank=True, null=True, verbose_name='Отчество')
    client_kind_ref = models.ForeignKey(
        ClientKind,
        on_delete=models.PROTECT,
        related_name='profiles',
        verbose_name='Вид клиента',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'client_profiles'
        verbose_name = 'Профиль клиента'
        verbose_name_plural = 'Профили клиентов'

    QUERY_ALIASES = {
        'client_kind': 'client_kind_ref__code',
        'client_kind_id': 'client_kind_ref_id',
    }
    objects = AliasManager()

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    def __init__(self, *args, **kwargs):
        legacy_client_kind = kwargs.pop('client_kind', None)
        self._legacy_registration_address = kwargs.pop('registration_address', None)
        self._legacy_actual_address = kwargs.pop('actual_address', None)
        self._legacy_notes = kwargs.pop('notes', None)
        self._legacy_preferred_contact_method = kwargs.pop('preferred_contact_method', None)
        has_client_kind_ref = 'client_kind_ref' in kwargs or 'client_kind_ref_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_client_kind not in (None, '') and not has_client_kind_ref:
            self.client_kind = legacy_client_kind

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'client_kind_ref', ClientKind)
        if self.user_id and self.user.user_type != 'client':
            raise ValidationError({'user': 'Профиль клиента можно привязать только к пользователю типа "Клиент".'})

    @property
    def client_kind(self) -> str | None:
        return self.client_kind_ref.code if self.client_kind_ref_id else None

    @client_kind.setter
    def client_kind(self, value):
        self.client_kind_ref = _resolve_lookup_instance(ClientKind, value)

    @property
    def preferred_contact_method(self):
        return self._legacy_preferred_contact_method

    @preferred_contact_method.setter
    def preferred_contact_method(self, value):
        self._legacy_preferred_contact_method = value

    @property
    def registration_address(self):
        return self._legacy_registration_address

    @registration_address.setter
    def registration_address(self, value):
        self._legacy_registration_address = value

    @property
    def actual_address(self):
        return self._legacy_actual_address

    @actual_address.setter
    def actual_address(self, value):
        self._legacy_actual_address = value

    @property
    def notes(self):
        return self._legacy_notes

    @notes.setter
    def notes(self, value):
        self._legacy_notes = value

    def save(self, *args, **kwargs):
        _ensure_lookup_default(self, 'client_kind_ref', ClientKind)
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


class ClientIndividualDetails(models.Model):
    """Паспортные данные клиента-физлица."""
    profile = models.OneToOneField(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='individual_details',
        verbose_name='Профиль клиента',
    )
    passport_series = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        validators=[passport_series_validator],
        verbose_name='Серия паспорта',
    )
    passport_number = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        validators=[passport_number_validator],
        verbose_name='Номер паспорта',
    )
    passport_issued_by = models.CharField(max_length=255, blank=True, null=True, verbose_name='Кем выдан')
    passport_issued_date = models.DateField(blank=True, null=True, verbose_name='Дата выдачи')
    passport_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        validators=[passport_code_validator],
        verbose_name='Код подразделения',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'client_individual_details'
        verbose_name = 'Паспортные данные клиента'
        verbose_name_plural = 'Паспортные данные клиентов'

    def __str__(self):
        return f'Паспортные данные: {self.profile}'


class ClientCompanyDetails(models.Model):
    """Реквизиты клиента-юрлица."""
    profile = models.OneToOneField(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='company_details',
        verbose_name='Профиль клиента',
    )
    company_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Название компании')
    company_inn = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        db_index=True,
        validators=[company_inn_validator],
        verbose_name='ИНН',
    )
    company_ogrn = models.CharField(
        max_length=13,
        blank=True,
        null=True,
        validators=[company_ogrn_validator],
        verbose_name='ОГРН',
    )
    company_kpp = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        validators=[company_kpp_validator],
        verbose_name='КПП',
    )
    legal_address = models.TextField(blank=True, null=True, verbose_name='Юридический адрес')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'client_company_details'
        verbose_name = 'Реквизиты юрлица'
        verbose_name_plural = 'Реквизиты юрлиц'

    def __str__(self):
        return f'Юрлицо: {self.profile}'


# =====================================================
# 5. НЕДВИЖИМОСТЬ И ДЕТАЛИ
# =====================================================

class BuildingDetails(models.Model):
    """Детали дома/строения."""
    house = models.OneToOneField(House, on_delete=models.CASCADE, related_name='building_details', verbose_name='Дом')
    year_built = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Год постройки')
    total_floors = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Всего этажей')
    building_material = models.ForeignKey(
        BuildingMaterial,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='Материал стен',
    )
    elevators_count = models.PositiveSmallIntegerField(default=0, verbose_name='Количество лифтов')

    class Meta:
        db_table = 'building_details'
        verbose_name = 'Детали дома'
        verbose_name_plural = 'Детали домов'

    def __str__(self):
        return f'Детали дома: {self.house}'


class Property(models.Model):
    """Объект недвижимости."""
    PROPERTY_TYPE_APARTMENT = 'apartment'
    PROPERTY_TYPE_HOUSE = 'house'
    PROPERTY_TYPE_COMMERCIAL = 'commercial'
    PROPERTY_TYPE_LAND = 'land'
    PROPERTY_TYPE_GARAGE = 'garage'
    PROPERTY_TYPE_ROOM = 'room'
    # Backward-compatible aliases kept for older forms / tests.
    PREMISES_APARTMENT = PROPERTY_TYPE_APARTMENT
    PREMISES_HOUSE = PROPERTY_TYPE_HOUSE
    PREMISES_COMMERCIAL = PROPERTY_TYPE_COMMERCIAL
    PREMISES_OFFICE = PROPERTY_TYPE_COMMERCIAL
    PREMISES_WAREHOUSE = PROPERTY_TYPE_COMMERCIAL
    PREMISES_TYPE_CHOICES = _lookup_choices(
        'PropertyType',
        (
            PROPERTY_TYPE_APARTMENT,
            PROPERTY_TYPE_HOUSE,
            PROPERTY_TYPE_COMMERCIAL,
            PROPERTY_TYPE_LAND,
            PROPERTY_TYPE_GARAGE,
            PROPERTY_TYPE_ROOM,
        ),
    )

    title = models.CharField(max_length=255, blank=True, null=True, verbose_name='Название')
    operation_type = models.ForeignKey(
        OperationType,
        on_delete=models.PROTECT,
        verbose_name='Тип операции',
        related_name='properties',
    )
    status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        verbose_name='Статус',
        related_name='properties',
        blank=True,
        null=True,
    )
    house = models.ForeignKey(
        House,
        on_delete=models.PROTECT,
        verbose_name='Дом',
        related_name='properties',
    )
    property_type_ref = models.ForeignKey(
        PropertyType,
        on_delete=models.PROTECT,
        verbose_name='Тип помещения',
        related_name='properties',
        blank=True,
        null=True,
    )
    coordinates_lat = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('-90')), MaxValueValidator(Decimal('90'))],
        verbose_name='Широта',
    )
    coordinates_lon = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('-180')), MaxValueValidator(Decimal('180'))],
        verbose_name='Долгота',
    )
    cadastral_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        validators=[cadastral_number_validator],
        verbose_name='Кадастровый номер',
    )
    price = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='Цена')
    area_total = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Общая площадь',
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    rooms_count = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='Количество комнат',
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    floor_number = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='Этаж',
        validators=[MinValueValidator(-5), MaxValueValidator(300)],
    )
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    is_published = models.BooleanField(default=True, verbose_name='Опубликовано')
    published_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата публикации')
    unpublished_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата снятия с публикации')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'properties'
        verbose_name = 'Объект недвижимости'
        verbose_name_plural = 'Объекты недвижимости'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='property_price_non_negative'),
            models.CheckConstraint(
                condition=models.Q(area_total__isnull=True) | models.Q(area_total__gt=0),
                name='property_area_total_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(rooms_count__isnull=True) | models.Q(rooms_count__gte=0),
                name='property_rooms_non_negative',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(coordinates_lat__isnull=True)
                    | (models.Q(coordinates_lat__gte=Decimal('-90')) & models.Q(coordinates_lat__lte=Decimal('90')))
                ),
                name='property_latitude_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(coordinates_lon__isnull=True)
                    | (models.Q(coordinates_lon__gte=Decimal('-180')) & models.Q(coordinates_lon__lte=Decimal('180')))
                ),
                name='property_longitude_range',
            ),
        ]

    QUERY_ALIASES = {
        'address': 'house',
        'address_id': 'house_id',
        'address__house': 'house',
        'address__house__street': 'house__street',
        'address__house__street__city': 'house__street__city',
        'owner': 'owners__client_profile__user',
        'owner_id': 'owners__client_profile__user_id',
        'total_floors': 'house__building_details__total_floors',
        'premises_type': 'property_type_ref__code',
        'premises_type_id': 'property_type_ref_id',
    }
    objects = AliasManager()

    def __init__(self, *args, **kwargs):
        legacy_premises_type = kwargs.pop('premises_type', None)
        legacy_address = kwargs.pop('address', None)
        legacy_owner = kwargs.pop('owner', None)
        legacy_owner_id = kwargs.pop('owner_id', None)
        legacy_total_floors = kwargs.pop('total_floors', None)
        has_property_type_ref = 'property_type_ref' in kwargs or 'property_type_ref_id' in kwargs
        has_house = 'house' in kwargs or 'house_id' in kwargs
        kwargs.pop('price_per_sqm', None)
        legacy_twogis = {
            'twogis_org_id': kwargs.pop('twogis_org_id', None),
            'twogis_name': kwargs.pop('twogis_name', None),
            'twogis_address_full': kwargs.pop('twogis_address_full', None),
            'twogis_rubric': kwargs.pop('twogis_rubric', None),
            'twogis_synced_at': kwargs.pop('twogis_synced_at', None),
        }
        super().__init__(*args, **kwargs)
        if legacy_premises_type not in (None, '') and not has_property_type_ref:
            self.premises_type = legacy_premises_type
        if legacy_address is not None and not has_house:
            self.address = legacy_address
        if legacy_owner not in (None, '') or legacy_owner_id not in (None, ''):
            self._pending_owner_profile = self._resolve_owner_profile(
                legacy_owner if legacy_owner not in (None, '') else legacy_owner_id,
            )
        if legacy_total_floors not in (None, ''):
            self.total_floors = legacy_total_floors
        for attr, value in legacy_twogis.items():
            if value not in (None, ''):
                setattr(self, attr, value)

    def __str__(self):
        return self.title or f'Объект в„–{self.pk}'

    @property
    def address(self):
        return self.house

    @address.setter
    def address(self, value):
        if isinstance(value, House):
            self.house = value
            return
        if hasattr(value, 'house'):
            self.house = value.house
            return
        if value in (None, ''):
            self.house = None
            return
        self.house = House.objects.filter(pk=value).first()

    def _resolve_owner_profile(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, PropertyOwner):
            return value.client_profile
        if isinstance(value, ClientProfile):
            return value
        if isinstance(value, User):
            return getattr(value, 'client_profile', None)
        if hasattr(value, 'client_profile'):
            return value.client_profile
        if hasattr(value, 'user') and isinstance(value.user, User):
            return value
        try:
            user_id = int(value)
        except (TypeError, ValueError):
            return None
        user = User.objects.select_related('client_profile').filter(pk=user_id).first()
        return getattr(user, 'client_profile', None) if user else None

    def _primary_owner_relation(self):
        if getattr(self, 'pk', None) is None:
            return None
        if hasattr(self, '_prefetched_objects_cache') and 'owners' in getattr(self, '_prefetched_objects_cache', {}):
            owners = list(self.owners.all())
            return owners[0] if owners else None
        return self.owners.select_related('client_profile__user').first()

    @property
    def owner_profile(self):
        relation = self._primary_owner_relation()
        return relation.client_profile if relation else None

    @property
    def owner(self):
        relation = self._primary_owner_relation()
        return relation.client_profile.user if relation and relation.client_profile_id else None

    @property
    def owner_id(self):
        relation = self._primary_owner_relation()
        return relation.client_profile.user_id if relation else None

    def is_owned_by(self, user) -> bool:
        if user in (None, '') or not getattr(user, 'pk', None):
            return False
        return self.owners.filter(client_profile__user_id=user.pk).exists()

    @property
    def premises_type(self) -> str | None:
        return self.property_type_ref.code if self.property_type_ref_id else None

    @premises_type.setter
    def premises_type(self, value):
        if value in {'office', 'warehouse'}:
            value = self.PROPERTY_TYPE_COMMERCIAL
        self.property_type_ref = _resolve_lookup_instance(PropertyType, value)

    @property
    def price_per_sqm(self) -> float | None:
        if not self.area_total:
            return None
        try:
            area = Decimal(str(self.area_total))
            if area <= 0:
                return None
            return float(Decimal(str(self.price)) / area)
        except Exception:
            return None

    @price_per_sqm.setter
    def price_per_sqm(self, value):
        return

    def _twogis_source(self):
        if hasattr(self, '_prefetched_objects_cache') and 'external_sources' in getattr(self, '_prefetched_objects_cache', {}):
            for source in self.external_sources.all():
                if source.source_name == '2gis':
                    return source
            return None
        return self.external_sources.filter(source_name='2gis').first()

    @property
    def twogis_org_id(self):
        source = self._twogis_source()
        return source.external_id if source else None

    @twogis_org_id.setter
    def twogis_org_id(self, value):
        source = self._twogis_source()
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id=str(value))
        if source is not None:
            source.external_id = str(value) if value not in (None, '') else ''
            self._pending_twogis_source = source

    @property
    def twogis_name(self):
        source = self._twogis_source()
        return source.source_object_name if source else None

    @twogis_name.setter
    def twogis_name(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.source_object_name = value
            self._pending_twogis_source = source

    @property
    def twogis_address_full(self):
        source = self._twogis_source()
        return source.source_address if source else None

    @twogis_address_full.setter
    def twogis_address_full(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.source_address = value
            self._pending_twogis_source = source

    @property
    def twogis_rubric(self):
        source = self._twogis_source()
        return source.source_rubric if source else None

    @twogis_rubric.setter
    def twogis_rubric(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.source_rubric = value
            self._pending_twogis_source = source

    @property
    def twogis_synced_at(self):
        source = self._twogis_source()
        return source.synced_at if source else None

    @twogis_synced_at.setter
    def twogis_synced_at(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.synced_at = value
            self._pending_twogis_source = source

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'status', PropertyStatus)
        _ensure_lookup_default(self, 'property_type_ref', PropertyType)
        errors = {}
        if self.price is not None and self.price < 0:
            errors['price'] = 'Цена не может быть отрицательной.'
        if self.area_total is not None and self.area_total <= 0:
            errors['area_total'] = 'Площадь должна быть больше нуля.'
        if self.premises_type == self.PROPERTY_TYPE_COMMERCIAL and self.rooms_count is not None:
            errors['rooms_count'] = 'Для офиса или склада количество комнат не используется.'
        if self.rooms_count is not None and self.rooms_count < 0:
            errors['rooms_count'] = 'Количество комнат не может быть отрицательным.'
        total_floors = self.total_floors
        if self.floor_number is not None and total_floors is not None:
            if self.floor_number > total_floors:
                errors['floor_number'] = 'Этаж объекта не может быть выше общего количества этажей дома.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields:
            update_fields = list(update_fields)
            if 'total_floors' in update_fields:
                update_fields = [field for field in update_fields if field != 'total_floors']
                if update_fields:
                    kwargs['update_fields'] = update_fields
                else:
                    kwargs.pop('update_fields')
        _ensure_lookup_default(self, 'status', PropertyStatus)
        _ensure_lookup_default(self, 'property_type_ref', PropertyType)
        _rewrite_legacy_update_fields(self, kwargs)
        pending_total_floors = getattr(self, '_pending_total_floors', None)
        has_pending_total_floors = hasattr(self, '_pending_total_floors')
        pending_owner_profile = getattr(self, '_pending_owner_profile', None)
        has_pending_owner_profile = hasattr(self, '_pending_owner_profile')
        with transaction.atomic():
            super().save(*args, **kwargs)
            if has_pending_total_floors:
                if self.house_id is not None:
                    details = BuildingDetails.objects.filter(house_id=self.house_id).first()
                    if details is not None or pending_total_floors not in (None, ''):
                        BuildingDetails.objects.update_or_create(
                            house_id=self.house_id,
                            defaults={'total_floors': pending_total_floors},
                        )
                delattr(self, '_pending_total_floors')
            if has_pending_owner_profile is True and pending_owner_profile is not None:
                owner_link, created = PropertyOwner.objects.get_or_create(
                    property=self,
                    client_profile=pending_owner_profile,
                    defaults={
                        'ownership_share': Decimal('100')
                        if not PropertyOwner.objects.filter(property=self).exclude(
                            client_profile=pending_owner_profile,
                        ).exists()
                        else None,
                    },
                )
                if created and owner_link.ownership_share is None:
                    existing = PropertyOwner.objects.filter(property=self).count()
                    if existing == 1:
                        owner_link.ownership_share = Decimal('100')
                        owner_link.save(update_fields=['ownership_share'])
                delattr(self, '_pending_owner_profile')
            pending_source = getattr(self, '_pending_twogis_source', None)
            if pending_source is not None:
                pending_source.property = self
                if any([
                    pending_source.external_id,
                    pending_source.source_object_name,
                    pending_source.source_address,
                    pending_source.source_rubric,
                    pending_source.synced_at,
                ]):
                    pending_source.save()

    @property
    def building_details(self):
        """Совместимость с деталями дома."""
        if getattr(self, 'house_id', None) is None:
            return None
        return BuildingDetails.objects.filter(house_id=self.house_id).first()

    @property
    def total_floors(self):
        if hasattr(self, '_pending_total_floors'):
            return self._pending_total_floors
        details = self.building_details
        if details is not None:
            return details.total_floors
        return None

    @total_floors.setter
    def total_floors(self, value):
        if value == '':
            value = None
        self._pending_total_floors = value
        details = self.building_details
        if details is not None:
            details.total_floors = value


class PropertyPriceHistory(models.Model):
    """История изменения цен объектов."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='price_history', verbose_name='Объект')
    old_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, verbose_name='Старая цена')
    new_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Новая цена')
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='Изменил', related_name='price_changes')
    changed_at = models.DateTimeField(default=timezone.now, verbose_name='Дата изменения')

    class Meta:
        db_table = 'property_price_history'
        verbose_name = 'История цен'
        verbose_name_plural = 'История цен'
        ordering = ['-changed_at']

    def __str__(self):
        return f'Цена объекта #{self.property_id}: {self.old_price} → {self.new_price}'


class PropertyStatusHistory(models.Model):
    """История смен статуса объекта недвижимости."""
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='Объект',
    )
    old_status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        related_name='property_status_history_old',
        blank=True,
        null=True,
        verbose_name='Старый статус',
    )
    new_status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        related_name='property_status_history_new',
        verbose_name='Новый статус',
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='property_status_changes',
        verbose_name='Изменил',
    )
    changed_at = models.DateTimeField(default=timezone.now, verbose_name='Дата изменения')

    class Meta:
        db_table = 'property_status_history'
        verbose_name = 'История статуса объекта'
        verbose_name_plural = 'История статусов объектов'
        ordering = ['-changed_at']

    def __str__(self):
        old_status = self.old_status.name if self.old_status_id else '—'
        new_status = self.new_status.name if self.new_status_id else '—'
        return f'Статус объекта #{self.property_id}: {old_status} → {new_status}'


class PropertyOwner(models.Model):
    """Собственник объекта недвижимости (поддерживает долевую собственность)."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='owners', verbose_name='Объект')
    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name='owned_properties', verbose_name='Собственник')
    ownership_share = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))],
        verbose_name='Доля собственности (%)',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        db_table = 'property_owners'
        verbose_name = 'Собственник объекта'
        verbose_name_plural = 'Собственники объектов'
        unique_together = [['property', 'client_profile']]
        ordering = ['created_at', 'property_id', 'client_profile_id']

    def __str__(self):
        share = f' ({self.ownership_share}%)' if self.ownership_share else ''
        return f'{self.property} в†’ {self.client_profile}{share}'


class PropertyDetails(models.Model):
    """Детальная информация об объекте недвижимости (для жилой недвижимости)."""
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='details', verbose_name='Объект')
    living_area = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Жилая площадь',
    )
    kitchen_area = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Площадь кухни',
    )
    ceiling_height = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Высота потолков (м)',
    )
    balcony_count = models.PositiveSmallIntegerField(default=0, verbose_name='Количество балконов/лоджий')
    bathroom_count = models.PositiveSmallIntegerField(default=1, verbose_name='Количество санузлов')
    bathroom_type = models.ForeignKey(
        BathroomType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='Тип санузла',
    )
    renovation_type = models.ForeignKey(
        RenovationType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='Тип ремонта',
    )
    bedrooms_count = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Количество спален')
    floors_count = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Количество этажей (для дома)')
    land_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Площадь участка',
    )

    class Meta:
        db_table = 'property_details'
        verbose_name = 'Детали объекта'
        verbose_name_plural = 'Детали объектов'

    def __str__(self):
        return f'Детали объекта #{self.property_id}'


class CommercialPropertyDetails(models.Model):
    """Детальная информация о коммерческой недвижимости."""
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='commercial_details', verbose_name='Объект')
    commercial_type = models.ForeignKey(
        CommercialPropertyType,
        on_delete=models.PROTECT,
        verbose_name='Тип коммерческой недвижимости',
    )
    usable_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Полезная площадь',
    )
    ceiling_height = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Высота потолков (м)',
    )
    floor_load = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Нагрузка на пол (кг/м²)',
    )
    electric_power_kw = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Электрическая мощность (кВт)',
    )
    has_separate_entrance = models.BooleanField(default=False, verbose_name='Отдельный вход')
    has_display_windows = models.BooleanField(default=False, verbose_name='Витринные окна')
    is_first_line = models.BooleanField(default=False, verbose_name='Первая линия домов')
    parking_spaces = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Парковочные места')

    class Meta:
        db_table = 'commercial_property_details'
        verbose_name = 'Детали коммерческой недвижимости'
        verbose_name_plural = 'Детали коммерческой недвижимости'

    def __str__(self):
        return f'Коммерческие детали объекта #{self.property_id}'


class PropertyAmenity(models.Model):
    """Связь объекта с удобствами/особенностями."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='amenities', verbose_name='Объект')
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE, verbose_name='Удобство')

    class Meta:
        db_table = 'property_amenities'
        verbose_name = 'Удобство объекта'
        verbose_name_plural = 'Удобства объектов'
        unique_together = [['property', 'amenity']]

    def __str__(self):
        return f'{self.property} в†’ {self.amenity}'


class PropertyPhoto(models.Model):
    """Фотография объекта."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 verbose_name='Объект',
                                 related_name='photos')
    url = models.TextField(blank=True, null=True, verbose_name='URL')
    caption = models.CharField(max_length=255, blank=True, null=True, verbose_name='Подпись')
    is_hidden = models.BooleanField(default=False, verbose_name='Скрыто')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='Дата загрузки')

    class Meta:
        db_table = 'property_photos'
        verbose_name = 'Фото объекта'
        verbose_name_plural = 'Фото объектов'
        ordering = ['order', '-uploaded_at']

    def __init__(self, *args, **kwargs):
        legacy_image = kwargs.pop('image', None)
        legacy_is_cover = kwargs.pop('is_cover', None)
        super().__init__(*args, **kwargs)
        if legacy_image not in (None, '') and not self.url:
            self.url = legacy_image if isinstance(legacy_image, str) else getattr(legacy_image, 'name', None)
        if legacy_is_cover not in (None, '') and bool(legacy_is_cover) and not getattr(self, 'order', None):
            self.order = 0

    @_property
    def is_cover(self):
        return self.order == 0

    @is_cover.setter
    def is_cover(self, value):
        if value:
            self.order = 0
        elif self.order == 0:
            self.order = 1


class PropertyDocument(models.Model):
    """Документ, привязанный к объекту (выписка ЕГРН, договор и т. п.)."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 verbose_name='Объект',
                                 related_name='documents')
    document_name = models.CharField(max_length=255, verbose_name='Название документа')
    file_url = models.TextField(verbose_name='URL файла')
    is_verified = models.BooleanField(default=False, verbose_name='Проверено')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    blank=True, null=True,
                                    verbose_name='Проверил',
                                    related_name='verified_documents')
    verified_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата проверки')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='Дата загрузки')

    class Meta:
        db_table = 'property_documents'
        verbose_name = 'Документ объекта'
        verbose_name_plural = 'Документы объектов'

    def clean(self):
        super().clean()
        errors = {}
        if self.is_verified and not self.verified_by_id:
            errors['verified_by'] = 'Для подтверждённого документа нужно указать проверившего сотрудника.'
        if self.verified_at and not self.is_verified:
            errors['verified_at'] = 'Дата проверки допускается только для подтверждённого документа.'
        if errors:
            raise ValidationError(errors)


class PropertyViewing(models.Model):
    """Запланированный просмотр объекта клиентом."""
    PAYMENT_REQUIRED_STATUS_CODES = ('confirmed', 'completed')
    PAYMENT_OPTIONAL_STATUS_CODES = ('cancelled', 'no_show')
    QUERY_ALIASES = {
        'client': 'client_profile__user',
        'client_id': 'client_profile__user_id',
        'agent': 'employee_profile__user',
        'agent_id': 'employee_profile__user_id',
    }
    objects = AliasManager()

    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                 verbose_name='Объект',
                                 related_name='viewings')
    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT,
                                       related_name='viewings',
                                       verbose_name='Клиент')
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT,
                                         related_name='viewings',
                                         verbose_name='Сотрудник')
    viewing_date = models.DateTimeField(verbose_name='Дата просмотра')
    status = models.ForeignKey(ViewingStatus, on_delete=models.PROTECT,
                               verbose_name='Статус', blank=True, null=True)
    comment = models.TextField(blank=True, null=True, verbose_name='Комментарий')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        db_table = 'property_viewings'
        verbose_name = 'Просмотр объекта'
        verbose_name_plural = 'Просмотры объектов'
        ordering = ['-viewing_date']

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'status', ViewingStatus)
        errors = {}
        if self.client_profile_id and self.client_profile.user.user_type != 'client':
            errors['client_profile'] = 'Клиентом просмотра может быть только пользователь типа "Клиент".'
        if self.employee_profile_id and self.employee_profile.user.user_type != 'employee':
            errors['employee_profile'] = 'Сотрудником просмотра может быть только сотрудник.'
        status_code = self.status.code if self.status_id else None
        payment = self.payment_object
        payment_status = payment.status if payment else None
        if (
            status_code in self.PAYMENT_REQUIRED_STATUS_CODES
            and payment_status != 'paid'
        ):
            errors['status'] = (
                'Нельзя перевести просмотр в статус '
                'подтвержденного/завершенного без подтверждённой оплаты.'
            )
        if errors:
            raise ValidationError(errors)

    @_property
    def client(self):
        return self.client_profile.user if self.client_profile_id else None

    @client.setter
    def client(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def client_id(self):
        return self.client_profile.user_id if self.client_profile_id else None

    @client_id.setter
    def client_id(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def agent(self):
        return self.employee_profile.user if self.employee_profile_id else None

    @agent.setter
    def agent(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def agent_id(self):
        return self.employee_profile.user_id if self.employee_profile_id else None

    @agent_id.setter
    def agent_id(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def scheduled_date(self):
        return self.viewing_date

    @scheduled_date.setter
    def scheduled_date(self, value):
        self.viewing_date = value

    @_property
    def notes(self):
        return self.comment

    @notes.setter
    def notes(self, value):
        self.comment = value

    @_property
    def payment_object(self):
        try:
            return self.payment
        except Exception:
            return None

    def save(self, *args, **kwargs):
        _ensure_lookup_default(self, 'status', ViewingStatus)
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


class ViewingPayment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает оплаты'),
        (STATUS_PAID, 'Оплачен'),
        (STATUS_FAILED, 'Ошибка оплаты'),
        (STATUS_REFUNDED, 'Возвращён'),
    ]

    viewing = models.OneToOneField(
        PropertyViewing,
        on_delete=models.PROTECT,
        related_name='payment',
        verbose_name='Просмотр',
    )
    client = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='viewing_payments',
        verbose_name='Клиент',
        limit_choices_to={'user_type_ref__code': 'client'},
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name='viewing_payments',
        verbose_name='Объект',
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма',
        validators=[MinValueValidator(Decimal('1.00')), MaxValueValidator(Decimal('100000.00'))],
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name='Статус оплаты',
    )
    sber_order_id = models.CharField(
        max_length=128,
        unique=True,
        blank=True,
        null=True,
        verbose_name='ID заказа Сбербанка',
    )
    sber_transaction_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name='ID транзакции Сбербанка',
    )
    payment_url = models.TextField(blank=True, null=True, verbose_name='Ссылка на оплату')
    paid_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата оплаты')
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'viewing_payments'
        verbose_name = 'Оплата просмотра'
        verbose_name_plural = 'Оплаты просмотров'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Оплата просмотра #{self.viewing_id} ({self.get_status_display()})'

    def clean(self):
        super().clean()
        errors = {}
        if self.client_id and self.client.user_type != 'client':
            errors['client'] = 'Плательщиком может быть только пользователь типа "Клиент".'
        if self.viewing_id:
            if self.client_id and self.viewing.client_profile.user_id != self.client_id:
                errors['client'] = 'Клиент оплаты должен совпадать с клиентом просмотра.'
            if self.property_id and self.viewing.property_id != self.property_id:
                errors['property'] = 'Объект оплаты должен совпадать с объектом просмотра.'
        if self.status == self.STATUS_PAID and not self.paid_at:
            errors['paid_at'] = 'Для оплаченного просмотра необходимо указать дату оплаты.'
        if self.status != self.STATUS_PAID and self.paid_at and self.status != self.STATUS_REFUNDED:
            errors['paid_at'] = 'Дата оплаты допустима только для оплаченного или возвращённого платежа.'
        if errors:
            raise ValidationError(errors)


class PaymentHistory(models.Model):
    payment = models.ForeignKey(
        ViewingPayment,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Платёж',
    )
    old_status = models.CharField(max_length=16, blank=True, null=True, verbose_name='Предыдущий статус')
    new_status = models.CharField(max_length=16, verbose_name='Новый статус')
    comment = models.TextField(blank=True, null=True, verbose_name='Комментарий')
    sber_response = models.JSONField(blank=True, null=True, verbose_name='Ответ Сбербанка')
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Дата создания')
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payment_history_changes',
        verbose_name='Изменил',
    )

    class Meta:
        db_table = 'payment_history'
        verbose_name = 'История оплаты просмотра'
        verbose_name_plural = 'История оплат просмотров'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'История платежа #{self.payment_id}: {self.old_status or "—"} → {self.new_status}'


class PropertyExternalSource(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='external_sources',
        verbose_name='Объект',
    )
    source_name = models.CharField(max_length=50, verbose_name='Источник')
    external_id = models.CharField(max_length=128, verbose_name='Внешний идентификатор')
    source_object_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Название объекта')
    source_address = models.TextField(blank=True, null=True, verbose_name='Адрес источника')
    source_rubric = models.CharField(max_length=255, blank=True, null=True, verbose_name='Рубрика источника')
    synced_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата синхронизации')

    class Meta:
        db_table = 'property_external_sources'
        verbose_name = 'Внешний источник объекта'
        verbose_name_plural = 'Внешние источники объектов'
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'source_name', 'external_id'],
                name='property_external_source_unique',
            ),
        ]

    def __str__(self):
        return f'{self.source_name}: {self.external_id}'


# =====================================================
# 6. Р—РђРЇР’РљР, РЎР”Р•Р›РљР, РЈР§РђРЎРўРќРРљР Р ДОКУМЕНТЫ
# =====================================================

class Request(models.Model):
    """Заявка клиента на подбор или конкретный объект."""
    LEGACY_STATUS_CODE_ALIASES = {
        'closed': 'completed',
    }
    STATUS_DISPLAY_NAMES = {
        'open': 'Открыта',
        'processing': 'В обработке',
        'completed': 'Завершена',
        'cancelled': 'Отменена',
        'rejected': 'Отклонена',
        'lost': 'Потеряна',
    }
    ACTIVE_STATUS_CODES = ('open', 'processing')
    TERMINAL_STATUS_CODES = (
        'completed', 'cancelled', 'rejected', 'lost',
    )
    SUCCESS_STATUS_CODES = ('completed',)

    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT,
                                       related_name='requests',
                                       verbose_name='Клиент')
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT,
                                         related_name='handled_requests',
                                         blank=True, null=True,
                                         verbose_name='Сотрудник')
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 related_name='direct_requests',
                                 verbose_name='Объект',
                                 blank=True, null=True)

    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       verbose_name='Тип операции',
                                       related_name='requests')
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT,
                               verbose_name='Статус',
                               related_name='requests',
                               blank=True, null=True)
    property_type = models.ForeignKey(PropertyType, on_delete=models.SET_NULL,
                                      blank=True, null=True,
                                      verbose_name='Тип помещения')
    preferred_city = models.ForeignKey(City, on_delete=models.SET_NULL,
                                       blank=True, null=True,
                                       verbose_name='Предпочитаемый город')
    preferred_district = models.CharField(max_length=100, blank=True, null=True, verbose_name='Предпочитаемый район')
    min_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
                                    validators=[MinValueValidator(0)], verbose_name='Минимальная цена')
    max_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
                                    validators=[MinValueValidator(0)], verbose_name='Максимальная цена')
    min_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True,
                                   verbose_name='Минимальная площадь',
                                   validators=[MinValueValidator(Decimal('0.01'))])
    max_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True,
                                   verbose_name='Максимальная площадь',
                                   validators=[MinValueValidator(Decimal('0.01'))])
    rooms_count = models.IntegerField(blank=True, null=True,
                                      verbose_name='Количество комнат',
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])

    address_preferences = models.TextField(blank=True, null=True, verbose_name='Пожелания по адресу')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    closed_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата закрытия')

    class Meta:
        db_table = 'requests'
        verbose_name = 'Заявка клиента'
        verbose_name_plural = 'Заявки клиентов'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_price__isnull=True) | models.Q(min_price__gte=0),
                name='request_min_price_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(max_price__isnull=True) | models.Q(max_price__gte=0),
                name='request_max_price_non_negative',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(min_price__isnull=True)
                    | models.Q(max_price__isnull=True)
                    | models.Q(min_price__lte=models.F('max_price'))
                ),
                name='request_price_range_valid',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(min_area__isnull=True)
                    | models.Q(max_area__isnull=True)
                    | models.Q(min_area__lte=models.F('max_area'))
                ),
                name='request_area_range_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(rooms_count__isnull=True) | models.Q(rooms_count__gte=0),
                name='request_rooms_non_negative',
            ),
        ]

    objects = AliasManager()
    QUERY_ALIASES = {
        'client': 'client_profile__user',
        'client_id': 'client_profile__user_id',
        'agent': 'employee_profile__user',
        'agent_id': 'employee_profile__user_id',
    }

    def __init__(self, *args, **kwargs):
        legacy_client = kwargs.pop('client', None)
        legacy_client_id = kwargs.pop('client_id', None)
        legacy_agent = kwargs.pop('agent', None)
        legacy_agent_id = kwargs.pop('agent_id', None)
        has_client_profile = 'client_profile' in kwargs or 'client_profile_id' in kwargs
        has_employee_profile = 'employee_profile' in kwargs or 'employee_profile_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_client not in (None, '') and not has_client_profile:
            self.client = legacy_client
        elif legacy_client_id not in (None, '') and not has_client_profile:
            self.client_id = legacy_client_id
        if legacy_agent not in (None, '') and not has_employee_profile:
            self.agent = legacy_agent
        elif legacy_agent_id not in (None, '') and not has_employee_profile:
            self.agent_id = legacy_agent_id

    def __str__(self):
        return f'Заявка в„–{self.pk} от {self.client_profile.user.username}'

    @_property
    def client(self):
        return self.client_profile.user if self.client_profile_id else None

    @client.setter
    def client(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def client_id(self):
        return self.client_profile.user_id if self.client_profile_id else None

    @client_id.setter
    def client_id(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def agent(self):
        return self.employee_profile.user if self.employee_profile_id else None

    @agent.setter
    def agent(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def agent_id(self):
        return self.employee_profile.user_id if self.employee_profile_id else None

    @agent_id.setter
    def agent_id(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'status', RequestStatus)
        errors = {}
        if self.client_profile_id and self.client_profile.user.user_type != 'client':
            errors['client_profile'] = 'В поле клиента можно выбрать только пользователя типа "Клиент".'
        if self.employee_profile_id and self.employee_profile.user.user_type != 'employee':
            errors['employee_profile'] = 'В поле сотрудника можно выбрать только сотрудника.'
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            errors['min_price'] = 'Минимальная цена не может быть больше максимальной.'
        if self.min_area is not None and self.max_area is not None and self.min_area > self.max_area:
            errors['min_area'] = 'Минимальная площадь не может быть больше максимальной.'
        if self.property_type and self.property_type.code == 'commercial' and self.rooms_count is not None:
            errors['rooms_count'] = 'Для офиса или склада количество комнат не используется.'
        if self.rooms_count is not None and self.rooms_count < 0:
            errors['rooms_count'] = 'Количество комнат не может быть отрицательным.'
        if self.closed_at and not self.status_id:
            errors['closed_at'] = 'Перед закрытием заявки нужно указать статус.'
        if errors:
            raise ValidationError(errors)

    @classmethod
    def normalize_status_code(cls, code: str | None) -> str | None:
        if code is None:
            return None
        return cls.LEGACY_STATUS_CODE_ALIASES.get(code, code)

    @classmethod
    def expand_status_filter_codes(
        cls,
        codes: list[str] | tuple[str, ...],
    ) -> tuple[str, ...]:
        expanded: list[str] = []
        reverse_aliases = {
            current: legacy
            for legacy, current in cls.LEGACY_STATUS_CODE_ALIASES.items()
        }
        for code in codes:
            normalized = (code or '').strip()
            if not normalized:
                continue
            for candidate in (
                normalized,
                cls.LEGACY_STATUS_CODE_ALIASES.get(normalized),
                reverse_aliases.get(normalized),
            ):
                if candidate and candidate not in expanded:
                    expanded.append(candidate)
        return tuple(expanded)

    @_property
    def status_code(self) -> str | None:
        if not self.status_id:
            return None
        return self.normalize_status_code(self.status.code)

    @_property
    def status_display_name(self) -> str | None:
        if not self.status_id:
            return None
        raw_code = self.status.code
        if raw_code in self.LEGACY_STATUS_CODE_ALIASES:
            normalized_code = self.normalize_status_code(raw_code)
            return self.STATUS_DISPLAY_NAMES.get(normalized_code, self.status.name)
        return self.status.name

    @_property
    def is_terminal(self) -> bool:
        return self.status_code in self.TERMINAL_STATUS_CODES

    def save(self, *args, **kwargs):
        _ensure_lookup_default(self, 'status', RequestStatus)
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


class RequestPropertyMatch(models.Model):
    """Вариант объекта по заявке клиента."""
    QUERY_ALIASES = {
        'agent': 'employee_profile__user',
        'agent_id': 'employee_profile__user_id',
        'request__client': 'request__client_profile__user',
        'request__client_id': 'request__client_profile__user_id',
        'request__agent': 'request__employee_profile__user',
        'request__agent_id': 'request__employee_profile__user_id',
    }
    objects = AliasManager()

    request = models.ForeignKey(Request, on_delete=models.CASCADE,
                                verbose_name='Заявка',
                                related_name='matches')
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 verbose_name='Объект',
                                 related_name='request_matches')
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT,
                                         related_name='proposed_matches',
                                         verbose_name='Сотрудник')
    status = models.ForeignKey(RequestMatchStatus, on_delete=models.PROTECT,
                               verbose_name='Статус', blank=True, null=True)
    agent_note = models.TextField(blank=True, null=True, verbose_name='Заметка сотрудника')
    confirmed_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата подтверждения')
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='confirmed_request_matches',
        limit_choices_to={'user_type_ref__code': 'employee'},
        verbose_name='Подтвердил',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        db_table = 'request_property_matches'
        verbose_name = 'Вариант по заявке'
        verbose_name_plural = 'Варианты по заявкам'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['request', 'property'],
                                    name='unique_request_property_match'),
        ]

    def __str__(self):
        return f'Заявка в„–{self.request_id} в†” объект в„–{self.property_id}'

    @_property
    def agent(self):
        return self.employee_profile.user if self.employee_profile_id else None

    @agent.setter
    def agent(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def agent_id(self):
        return self.employee_profile.user_id if self.employee_profile_id else None

    @agent_id.setter
    def agent_id(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def state_code(self) -> str:
        if self.status_id:
            return self.status.code
        return 'draft'

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'status', RequestMatchStatus)
        errors = {}
        if self.employee_profile_id and self.employee_profile.user.user_type != 'employee':
            errors['employee_profile'] = 'Сотрудником варианта может быть только сотрудник.'
        if self.confirmed_by_id and self.confirmed_by.user_type != 'employee':
            errors['confirmed_by'] = 'Подтвердить вариант может только сотрудник.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        _ensure_lookup_default(self, 'status', RequestMatchStatus)
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


class Deal(models.Model):
    """Сделка по объекту и клиенту."""
    deal_number = models.CharField(max_length=50, unique=True, verbose_name='Номер сделки')
    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                 verbose_name='Объект',
                                 related_name='deals')
    client = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='client_deals',
        verbose_name='Клиент',
        blank=True,
        null=True,
        limit_choices_to={'user_type_ref__code': 'client'},
    )
    agent = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='agent_deals',
        verbose_name='Агент',
        blank=True,
        null=True,
        limit_choices_to={'user_type_ref__code': 'employee'},
    )
    employee_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name='deals',
        verbose_name='Сотрудник',
        blank=True,
        null=True,
    )
    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       verbose_name='Тип операции',
                                       related_name='deals')
    status = models.ForeignKey(DealStatus, on_delete=models.PROTECT,
                               related_name='deals',
                               verbose_name='Статус',
                               blank=True, null=True)

    request = models.OneToOneField(
        Request, on_delete=models.SET_NULL,
        related_name='deal', blank=True, null=True,
        verbose_name='Заявка',
    )

    price_final = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='Итоговая цена')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                             blank=True, null=True,
                                             verbose_name='Процент комиссии',
                                             validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    commission_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Сумма комиссии',
    )
    deal_date = models.DateField(verbose_name='Дата сделки')
    notes = models.TextField(blank=True, null=True, verbose_name='Примечания')

    contract_status_ref = models.ForeignKey(
        ContractStatus,
        on_delete=models.PROTECT,
        related_name='deals',
        verbose_name='Статус договора',
        blank=True,
        null=True,
    )
    contract_file = models.FileField(
        upload_to='deals/contracts/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Файл договора',
    )
    contract_error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Причина ошибки договора',
    )
    contract_requested_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата запроса договора',
    )
    contract_processing_started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата начала формирования договора',
    )
    contract_generated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата формирования договора',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'deals'
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'
        ordering = ['-deal_date']
        constraints = [
            models.CheckConstraint(condition=models.Q(price_final__gte=0), name='deal_price_final_non_negative'),
            models.CheckConstraint(
                condition=(
                    models.Q(commission_percent__isnull=True)
                    | (models.Q(commission_percent__gte=Decimal('0')) & models.Q(commission_percent__lte=Decimal('100')))
                ),
                name='deal_commission_percent_range',
            ),
            models.CheckConstraint(
                condition=models.Q(commission_amount__isnull=True) | models.Q(commission_amount__gte=0),
                name='deal_commission_amount_non_negative',
            ),
        ]

    QUERY_ALIASES = {
        'contract_status': 'contract_status_ref__code',
        'contract_status_id': 'contract_status_ref_id',
    }
    objects = AliasManager()

    def __str__(self):
        return f'Сделка {self.deal_number}'

    def __init__(self, *args, **kwargs):
        legacy_contract_status = kwargs.pop('contract_status', None)
        has_contract_status_ref = (
            'contract_status_ref' in kwargs or 'contract_status_ref_id' in kwargs
        )
        super().__init__(*args, **kwargs)
        if legacy_contract_status not in (None, '') and not has_contract_status_ref:
            self.contract_status = legacy_contract_status

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'contract_status_ref', ContractStatus)
        errors = {}
        if self.client_id and self.client.user_type != 'client':
            errors['client'] = 'Клиентом сделки может быть только пользователь типа "Клиент".'
        if self.agent_id and self.agent.user_type != 'employee':
            errors['agent'] = 'Агентом сделки может быть только сотрудник.'
        if self.employee_profile_id and self.employee_profile.user.user_type != 'employee':
            errors['employee_profile'] = 'Сотрудником сделки может быть только сотрудник.'
        if self.request_id and self.client_id and self.request.client_profile.user_id != self.client_id:
            errors['client'] = 'Клиент сделки должен совпадать с клиентом заявки.'
        if self.request_id and self.agent_id and self.request.employee_profile_id:
            request_agent_user_id = self.request.employee_profile.user_id
            if request_agent_user_id != self.agent_id:
                errors['agent'] = 'Агент сделки должен совпадать с сотрудником заявки.'
        if self.price_final is not None and self.price_final < 0:
            errors['price_final'] = 'Итоговая цена не может быть отрицательной.'
        if self.commission_percent is not None and not (Decimal('0') <= self.commission_percent <= Decimal('100')):
            errors['commission_percent'] = 'Процент комиссии должен быть от 0 до 100.'
        if self.commission_amount is not None and self.commission_amount < 0:
            errors['commission_amount'] = 'Сумма комиссии не может быть отрицательной.'
        if self.contract_status == 'ready' and not self.contract_file:
            errors['contract_file'] = 'Для статуса "Готов" нужно прикрепить файл договора.'
        if self.contract_status == 'failed' and not self.contract_error_message:
            errors['contract_error_message'] = 'Для статуса ошибки нужно указать причину.'
        if errors:
            raise ValidationError(errors)

    @_property
    def contract_status(self) -> str | None:
        return self.contract_status_ref.code if self.contract_status_ref_id else None

    @contract_status.setter
    def contract_status(self, value):
        self.contract_status_ref = _resolve_lookup_instance(ContractStatus, value)

    def get_contract_status_display(self) -> str:
        if not self.contract_status_ref_id:
            return ''
        return self.contract_status_ref.name

    def save(self, *args, **kwargs):
        _ensure_lookup_default(self, 'contract_status_ref', ContractStatus)
        _rewrite_legacy_update_fields(self, kwargs)
        if self.client_id is None and self.request_id:
            self.client = self.request.client_profile.user
        if self.agent_id is None:
            if self.employee_profile_id:
                self.agent = self.employee_profile.user
            elif self.request_id and self.request.employee_profile_id:
                self.agent = self.request.employee_profile.user
        if self.employee_profile_id is None and self.agent_id and hasattr(self.agent, 'employee_profile'):
            self.employee_profile = self.agent.employee_profile
        if self.commission_amount is None and self.price_final is not None and self.commission_percent is not None:
            self.commission_amount = (
                Decimal(str(self.price_final))
                * Decimal(str(self.commission_percent))
                / Decimal('100')
            ).quantize(Decimal('0.01'))
        return super().save(*args, **kwargs)


class DealParticipant(models.Model):
    """Участник сделки (клиент с ролью)."""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='participants', verbose_name='Сделка')
    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name='deals', verbose_name='Клиент')
    role = models.ForeignKey(DealParticipantRole, on_delete=models.PROTECT, verbose_name='Роль')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        db_table = 'deal_participants'
        verbose_name = 'Участник сделки'
        verbose_name_plural = 'Участники сделок'
        unique_together = [['deal', 'client_profile', 'role']]

    def __str__(self):
        return f'{self.deal.deal_number} в†’ {self.client_profile} ({self.role})'


class DealDocument(models.Model):
    """Документ сделки."""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='documents', verbose_name='Сделка')
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, verbose_name='Тип документа')
    file_url = models.TextField(blank=True, null=True, verbose_name='URL файла')
    document_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='Номер документа')
    template_path = models.CharField(max_length=255, blank=True, null=True, verbose_name='Путь к шаблону')
    generated_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата генерации')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Сгенерировал')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        db_table = 'deal_documents'
        verbose_name = 'Документ сделки'
        verbose_name_plural = 'Документы сделок'

    def __str__(self):
        return f'{self.deal.deal_number} в†’ {self.document_type.name}'


class Task(models.Model):
    """Задача сотрудника."""
    TERMINAL_STATUS_CODES = ('done', 'cancelled')
    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = _lookup_choices(
        'TaskPriority',
        (
            PRIORITY_LOW,
            PRIORITY_NORMAL,
            PRIORITY_HIGH,
        ),
    )
    TASK_TYPE_CONTACT_CLIENT = 'contact_client'
    TASK_TYPE_PROPERTY_SEARCH = 'property_search'
    TASK_TYPE_SHOWING = 'showing'
    TASK_TYPE_DOCUMENTS = 'documents'
    TASK_TYPE_CALL = 'call'
    TASK_TYPE_OTHER = 'other'
    TASK_TYPE_CHOICES = _lookup_choices(
        'TaskType',
        (
            TASK_TYPE_CONTACT_CLIENT,
            TASK_TYPE_PROPERTY_SEARCH,
            TASK_TYPE_SHOWING,
            TASK_TYPE_DOCUMENTS,
            TASK_TYPE_CALL,
            TASK_TYPE_OTHER,
        ),
    )

    title = models.CharField(max_length=255, verbose_name='Название')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    priority_ref = models.ForeignKey(
        TaskPriority,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name='Приоритет',
        blank=True,
        null=True,
    )
    task_type_ref = models.ForeignKey(
        TaskType,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name='Тип задач',
        blank=True,
        null=True,
    )
    status = models.ForeignKey(TaskStatus, on_delete=models.PROTECT,
                               verbose_name='Статус',
                               related_name='tasks')

    assignee = models.ForeignKey(User, on_delete=models.PROTECT,
                                 related_name='assigned_tasks',
                                 verbose_name='Исполнитель',
                                 limit_choices_to={'user_type_ref__code': 'employee'})
    created_by = models.ForeignKey(User, on_delete=models.PROTECT,
                                   verbose_name='Создатель',
                                   related_name='created_tasks')

    client_profile = models.ForeignKey(ClientProfile, on_delete=models.SET_NULL,
                                       blank=True, null=True,
                                       related_name='tasks',
                                       verbose_name='Клиент')
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 verbose_name='Объект',
                                 blank=True, null=True, related_name='tasks')
    request = models.ForeignKey(Request, on_delete=models.SET_NULL,
                                verbose_name='Заявка',
                                blank=True, null=True, related_name='tasks')
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL,
                             verbose_name='Сделка',
                             blank=True, null=True, related_name='tasks')

    due_date = models.DateTimeField(blank=True, null=True, verbose_name='Срок')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='Закрыта')
    result = models.TextField(blank=True, null=True,
                              verbose_name='Результат',
                              help_text='Результат выполнения задачи')
    steps_log = models.JSONField(
        default=list, blank=True,
        help_text='Журнал этапов выполнения (список объектов).',
        verbose_name='Журнал этапов',
    )
    is_auto_closed = models.BooleanField(default=False,
                                         verbose_name='Закрыта автоматически',
                                         help_text='Закрыта автоматически системой')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'tasks'
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']

    QUERY_ALIASES = {
        'priority': 'priority_ref__code',
        'priority_id': 'priority_ref_id',
        'task_type': 'task_type_ref__code',
        'task_type_id': 'task_type_ref_id',
        'client': 'client_profile__user',
        'client_id': 'client_profile__user_id',
    }
    objects = AliasManager()

    def __str__(self):
        return self.title

    @_property
    def client(self):
        return self.client_profile.user if self.client_profile_id else None

    @client.setter
    def client(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def client_id(self):
        return self.client_profile.user_id if self.client_profile_id else None

    @client_id.setter
    def client_id(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    def __init__(self, *args, **kwargs):
        legacy_priority = kwargs.pop('priority', None)
        legacy_task_type = kwargs.pop('task_type', None)
        has_priority_ref = 'priority_ref' in kwargs or 'priority_ref_id' in kwargs
        has_task_type_ref = 'task_type_ref' in kwargs or 'task_type_ref_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_priority not in (None, '') and not has_priority_ref:
            self.priority = legacy_priority
        if legacy_task_type not in (None, '') and not has_task_type_ref:
            self.task_type = legacy_task_type

    def clean(self):
        super().clean()
        _ensure_lookup_default(self, 'priority_ref', TaskPriority)
        _ensure_lookup_default(self, 'task_type_ref', TaskType)
        errors = {}
        if self.assignee_id and self.assignee.user_type != 'employee':
            errors['assignee'] = 'Исполнителем задачи может быть только сотрудник.'
        if self.created_by_id and self.created_by.user_type != 'employee':
            errors['created_by'] = 'Создателем задачи должен быть сотрудник.'
        if self.client_profile_id and self.client_profile.user.user_type != 'client':
            errors['client_profile'] = 'В поле клиента можно выбрать только пользователя типа "Клиент".'
        if self.completed_at and self.status_id and self.status.code not in self.TERMINAL_STATUS_CODES:
            errors['completed_at'] = 'Дата завершения допускается только для финального статуса задачи.'
        if errors:
            raise ValidationError(errors)

    @_property
    def is_completed(self):
        return (self.status_id is not None
                and self.status.code in self.TERMINAL_STATUS_CODES)

    @_property
    def is_terminal(self):
        return self.is_completed

    @_property
    def task_type_display(self):
        if not self.task_type_ref_id:
            return self.task_type or ''
        return self.task_type_ref.name

    @_property
    def priority(self) -> str | None:
        return self.priority_ref.code if self.priority_ref_id else None

    @priority.setter
    def priority(self, value):
        self.priority_ref = _resolve_lookup_instance(TaskPriority, value)

    def get_priority_display(self) -> str:
        if not self.priority_ref_id:
            return ''
        return self.priority_ref.name

    @_property
    def task_type(self) -> str | None:
        return self.task_type_ref.code if self.task_type_ref_id else None

    @task_type.setter
    def task_type(self, value):
        self.task_type_ref = _resolve_lookup_instance(TaskType, value)

    def get_task_type_display(self) -> str:
        if not self.task_type_ref_id:
            return ''
        return self.task_type_ref.name

    def save(self, *args, **kwargs):
        _ensure_lookup_default(self, 'priority_ref', TaskPriority)
        _ensure_lookup_default(self, 'task_type_ref', TaskType)
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


# =====================================================
# 7. АУДИТ, ПОЧТА, РЕЗЕРВНОЕ КОПИРОВАНИЕ
# =====================================================

class OutgoingEmail(models.Model):
    """Очередь исходящих писем."""
    STATUS_CHOICES = [
        ('processing', 'Обрабатывается'),
        ('pending', 'Ожидает отправки'),
        ('sent', 'Отправлено'),
        ('failed', 'Ошибка отправки'),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='outgoing_emails',
        verbose_name='Получатель',
    )
    sender = models.ForeignKey(User, on_delete=models.SET_NULL,
                               blank=True, null=True,
                               related_name='sent_emails',
                               verbose_name='Отправитель',
                               limit_choices_to={'user_type_ref__code': 'employee'})
    subject = models.CharField(max_length=255, verbose_name='Тема')
    body = models.TextField(verbose_name='Текст письма')
    html_body = models.TextField(blank=True, default='', verbose_name='HTML-текст')
    trigger_code = models.CharField(max_length=64, blank=True, null=True, db_index=True, verbose_name='Trigger code')
    context = models.JSONField(default=dict, blank=True, verbose_name='Контекст')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              verbose_name='Статус',
                              default='pending', db_index=True)

    task = models.ForeignKey(Task, on_delete=models.SET_NULL,
                             verbose_name='Задача',
                             blank=True, null=True, related_name='emails')
    request = models.ForeignKey(Request, on_delete=models.SET_NULL,
                                verbose_name='Заявка',
                                blank=True, null=True, related_name='emails')
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 verbose_name='Объект',
                                 blank=True, null=True, related_name='emails')

    error_message = models.TextField(blank=True, null=True, verbose_name='Error message')
    processing_started_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата начала обработки')
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата отправки')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        db_table = 'outgoing_emails'
        verbose_name = 'Исходящее письмо'
        verbose_name_plural = 'Исходящие письма'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=['processing', 'pending', 'sent', 'failed']),
                name='outgoing_email_status_valid',
            ),
        ]

    def __str__(self):
        return f'{self.subject} в†’ {self.recipient.email}'

    def clean(self):
        super().clean()
        errors = {}
        if self.sender_id and self.sender.user_type != 'employee':
            errors['sender'] = 'Отправителем может быть только сотрудник.'
        if self.status == 'sent' and not self.sent_at:
            errors['sent_at'] = 'Для отправленного письма нужно указать дату отправки.'
        if self.status == 'failed' and not self.error_message:
            errors['error_message'] = 'Для ошибки отправки нужно указать причину.'
        if errors:
            raise ValidationError(errors)


class AuditLog(models.Model):
    """Единый журнал значимых действий системы."""

    QUERY_ALIASES = {
        'entity_type': 'entity_type__code',
        'action_code': 'action__code',
        'action_label': 'action__name',
        'entity_type_code': 'entity_type__code',
        'entity_type_name': 'entity_type__name',
    }

    entity_type = models.ForeignKey(AuditEntityType, on_delete=models.PROTECT, verbose_name='Тип сущности')
    entity_id = models.PositiveIntegerField(db_index=True, verbose_name='Идентификатор сущности')
    action = models.ForeignKey(AuditAction, on_delete=models.PROTECT, verbose_name='Действие')
    message = models.TextField(verbose_name='Сообщение')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Метаданные')

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        verbose_name='Инициатор',
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Дата создания')
    objects = AliasManager()

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Запись журнала'
        verbose_name_plural = 'Журнал действий'
        ordering = ['-created_at', '-id']

    @property
    def action_code(self):
        return self.action.code if self.action_id else None

    @property
    def action_label(self):
        return self.action.name if self.action_id else ''

    def get_entity_type_display(self):
        return self.entity_type.name if self.entity_type_id else ''

    @property
    def property(self):
        return None

    @_property
    def request(self):
        return None

    @_property
    def task(self):
        return None

    @_property
    def deal(self):
        return None

    def __str__(self):
        return f'{self.entity_type.name} #{self.entity_id}: {self.action.name}'


class DatabaseBackup(models.Model):
    """Сохраненный файл полной резервной копии базы данных."""

    filename = models.CharField(max_length=255, verbose_name='Имя файла')
    file = models.FileField(
        storage=database_backup_storage,
        upload_to='database_backups/%Y/%m/',
        verbose_name='Файл',
    )
    size_bytes = models.PositiveBigIntegerField(default=0, verbose_name='Size bytes')
    database_name = models.CharField(max_length=255, verbose_name='Название базы данных')
    engine_label = models.CharField(max_length=120, verbose_name='СУБД')
    tool_label = models.CharField(max_length=120, blank=True, default='', verbose_name='Инструмент')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='database_backups',
        verbose_name='Создатель',
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Дата создания')

    class Meta:
        db_table = 'database_backups'
        verbose_name = 'Резервная копия БД'
        verbose_name_plural = 'Резервные копии БД'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.filename
