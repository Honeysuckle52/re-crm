"""ORM-модели приложения ``key``."""
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from .storage import database_backup_storage

# Поле ``Task.property`` перекрывает builtins.property.
_property = property

phone_validator = RegexValidator(
    regex=r'^\+7\d{10}$',
    message='Телефон должен быть российским номером в формате +7XXXXXXXXXX.',
)
username_validator = RegexValidator(
    regex=r'^[\w.@+-]+$',
    message='Логин может содержать только буквы, цифры и символы @/./+/-/_.',
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


LOOKUP_NAME_DEFAULTS = {
    'PropertyType': {
        'apartment': 'Квартира',
        'house': 'Дом',
        'office': 'Офис',
        'warehouse': 'Склад',
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


def _lookup_default_name(model_class, code: str) -> str:
    return LOOKUP_NAME_DEFAULTS.get(model_class.__name__, {}).get(code, code)


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
        return super().update(**self._rewrite_update_kwargs(kwargs))


class AliasManager(models.Manager):
    def get_queryset(self):
        return AliasQuerySet(self.model, using=self._db, hints=self._hints)


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


class UserRole(models.Model):
    """Роль сотрудника в системе (администратор / менеджер / агент)."""
    code = models.CharField(max_length=20, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    max_active_tasks = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Максимум активных задач',
    )
    max_in_progress_tasks = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Максимум задач в работе',
    )
    max_active_requests = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Максимум активных заявок',
    )

    class Meta:
        db_table = 'user_roles'
        verbose_name = 'Роль пользователя'
        verbose_name_plural = 'Роли пользователей'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_active_tasks__gte=0)
                & models.Q(max_active_tasks__lte=100)
                & models.Q(max_in_progress_tasks__gte=0)
                & models.Q(max_in_progress_tasks__lte=100)
                & models.Q(max_active_requests__gte=0)
                & models.Q(max_active_requests__lte=100),
                name='user_role_limits_in_range',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.max_in_progress_tasks > self.max_active_tasks:
            raise ValidationError({
                'max_in_progress_tasks': 'Лимит задач в работе не может быть больше общего лимита активных задач.',
            })

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
        validators=[username_validator],
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
        default=1,
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
                'role': 'Роль назначается только сотрудникам.',
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
    first_name = models.CharField(max_length=50, verbose_name='First name')
    last_name = models.CharField(max_length=50, verbose_name='Last name')
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name='Position')
    hire_date = models.DateField(blank=True, null=True, verbose_name='Hire date')
    internal_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Internal phone')
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
    CLIENT_KIND_CHOICES = [
        (CLIENT_KIND_INDIVIDUAL, 'Физическое лицо'),
        (CLIENT_KIND_COMPANY, 'Юридическое лицо'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                    verbose_name='Пользователь',
                                related_name='client_profile')
    first_name = models.CharField(max_length=50, verbose_name='First name')
    last_name = models.CharField(max_length=50, verbose_name='Last name')
    middle_name = models.CharField(max_length=50, blank=True, null=True, verbose_name='Middle name')
    client_kind_ref = models.ForeignKey(
        ClientKind,
        on_delete=models.PROTECT,
        related_name='profiles',
        verbose_name='Вид клиента',
        default=1,
    )
    contact_method = models.ForeignKey(
        ContactMethod,
        on_delete=models.SET_NULL,
        related_name='profiles',
        blank=True,
        null=True,
        verbose_name='Предпочтительный способ связи',
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
        'preferred_contact_method': 'contact_method__code',
        'preferred_contact_method_id': 'contact_method_id',
    }
    objects = AliasManager()

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    def __init__(self, *args, **kwargs):
        legacy_client_kind = kwargs.pop('client_kind', None)
        legacy_contact_method = kwargs.pop('preferred_contact_method', None)
        self._legacy_registration_address = kwargs.pop('registration_address', None)
        self._legacy_actual_address = kwargs.pop('actual_address', None)
        self._legacy_notes = kwargs.pop('notes', None)
        has_client_kind_ref = 'client_kind_ref' in kwargs or 'client_kind_ref_id' in kwargs
        has_contact_method = 'contact_method' in kwargs or 'contact_method_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_client_kind not in (None, '') and not has_client_kind_ref:
            self.client_kind = legacy_client_kind
        if legacy_contact_method not in (None, '') and not has_contact_method:
            self.preferred_contact_method = legacy_contact_method

    def clean(self):
        super().clean()
        if self.user_id and self.user.user_type != 'client':
            raise ValidationError({'user': 'Профиль клиента можно привязать только к пользователю типа "Клиент".'})

    @property
    def client_kind(self) -> str | None:
        return self.client_kind_ref.code if self.client_kind_ref_id else None

    @client_kind.setter
    def client_kind(self, value):
        self.client_kind_ref = _resolve_lookup_instance(ClientKind, value)

    @property
    def preferred_contact_method(self) -> str | None:
        return self.contact_method.code if self.contact_method_id else None

    @preferred_contact_method.setter
    def preferred_contact_method(self, value):
        self.contact_method = _resolve_lookup_instance(ContactMethod, value)

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
        verbose_name='Passport series',
    )
    passport_number = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        validators=[passport_number_validator],
        verbose_name='Passport number',
    )
    passport_issued_by = models.CharField(max_length=255, blank=True, null=True, verbose_name='Passport issued by')
    passport_issued_date = models.DateField(blank=True, null=True, verbose_name='Passport issued date')
    passport_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        validators=[passport_code_validator],
        verbose_name='Passport code',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'client_individual_details'
        verbose_name = 'Паспортные данные клиента'
        verbose_name_plural = 'Паспортные данные клиентов'

    def __str__(self):
        return f'Паспортные данные: {self.profile}'

    def clean(self):
        super().clean()


class ClientCompanyDetails(models.Model):
    """Реквизиты клиента-юрлица."""
    profile = models.OneToOneField(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='company_details',
        verbose_name='Профиль клиента',
    )
    company_inn = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        db_index=True,
        validators=[company_inn_validator],
        verbose_name='Company inn',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        db_table = 'client_company_details'
        verbose_name = 'Реквизиты юрлица'
        verbose_name_plural = 'Реквизиты юрлиц'

    def __str__(self):
        return f'Юрлицо: {self.profile}'

class Property(models.Model):
    PREMISES_APARTMENT = 'apartment'
    PREMISES_HOUSE = 'house'
    PREMISES_OFFICE = 'office'
    PREMISES_WAREHOUSE = 'warehouse'
    PREMISES_TYPE_CHOICES = [
        (PREMISES_APARTMENT, 'Квартира'),
        (PREMISES_HOUSE, 'Дом'),
        (PREMISES_OFFICE, 'Офис'),
        (PREMISES_WAREHOUSE, 'Склад'),
    ]

    """Объект недвижимости."""
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
        default=1,
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
        default=1,
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='owned_properties',
        limit_choices_to={'user_type_ref__code': 'client'},
        blank=True,
        null=True,
        verbose_name='Владелец',
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
    price = models.FloatField(validators=[MinValueValidator(0)], verbose_name='Цена')
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
    total_floors = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='Всего этажей',
        validators=[MinValueValidator(0), MaxValueValidator(300)],
    )
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
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
                    models.Q(total_floors__isnull=True)
                    | models.Q(floor_number__isnull=True)
                    | models.Q(floor_number__lte=models.F('total_floors'))
                ),
                name='property_floor_not_above_total',
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
        'premises_type': 'property_type_ref__code',
        'premises_type_id': 'property_type_ref_id',
    }
    objects = AliasManager()

    def __init__(self, *args, **kwargs):
        legacy_premises_type = kwargs.pop('premises_type', None)
        legacy_address = kwargs.pop('address', None)
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
        for attr, value in legacy_twogis.items():
            if value not in (None, ''):
                setattr(self, attr, value)

    def __str__(self):
        return self.title or f'Объект №{self.pk}'

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

    @property
    def premises_type(self) -> str | None:
        return self.property_type_ref.code if self.property_type_ref_id else None

    @premises_type.setter
    def premises_type(self, value):
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
        # Поле больше не хранится в БД; старые вызовы create/update игнорируем.
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
        errors = {}
        if self.price is not None and self.price < 0:
            errors['price'] = 'Цена не может быть отрицательной.'
        if self.area_total is not None and self.area_total <= 0:
            errors['area_total'] = 'Площадь должна быть больше нуля.'
        if self.premises_type in {self.PREMISES_OFFICE, self.PREMISES_WAREHOUSE} and self.rooms_count is not None:
            errors['rooms_count'] = 'Для офиса или склада количество комнат не используется.'
        if self.rooms_count is not None and self.rooms_count < 0:
            errors['rooms_count'] = 'Количество комнат не может быть отрицательным.'
        if self.floor_number is not None and self.total_floors is not None and self.floor_number > self.total_floors:
            errors['floor_number'] = 'Этаж объекта не может быть выше общего количества этажей.'
        if self.owner_id and self.owner.user_type != 'client':
            errors['owner'] = 'Owner must be a client user.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        _rewrite_legacy_update_fields(self, kwargs)
        super().save(*args, **kwargs)
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



class PropertyPhoto(models.Model):
    """Фотография объекта."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                     verbose_name='Объект',
                                 related_name='photos')
    image = models.ImageField(upload_to='%Y/%m/',
                                  verbose_name='Изображение',
                              blank=True, null=True)
    url = models.TextField(blank=True, null=True, verbose_name='URL')
    caption = models.CharField(max_length=255, blank=True, null=True, verbose_name='Подпись')
    is_cover = models.BooleanField(default=False, verbose_name='Обложка')
    is_hidden = models.BooleanField(default=False, verbose_name='Скрыто')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='Дата загрузки')

    class Meta:
        db_table = 'property_photos'
        verbose_name = 'Фото объекта'
        verbose_name_plural = 'Фото объектов'
        ordering = ['-is_cover', 'order', '-uploaded_at']

    def clean(self):
        super().clean()
        errors = {}
        if not self.image and not self.url:
            errors['image'] = 'Добавьте файл изображения или укажите URL фотографии.'
        if self.is_cover and self.property_id:
            covers = PropertyPhoto.objects.filter(property_id=self.property_id, is_cover=True)
            if self.pk:
                covers = covers.exclude(pk=self.pk)
            if covers.exists():
                errors['is_cover'] = 'У объекта может быть только одна обложка.'
        if errors:
            raise ValidationError(errors)


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

    client = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='client_requests',
                                   verbose_name='Клиент',
                               limit_choices_to={'user_type_ref__code': 'client'})
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_requests',
                              blank=True, null=True,
                                  verbose_name='Агент',
                              limit_choices_to={'user_type_ref__code': 'employee'})
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 related_name='direct_requests',
                                     verbose_name='Объект',
                                 blank=True, null=True)

    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                           verbose_name='Тип операции',
                                       related_name='requests')
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT,
                                   verbose_name='Статус',
                               related_name='requests', default=1)
    property_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='Тип помещения')
    min_price = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)], verbose_name='Минимальная цена')
    max_price = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)], verbose_name='Максимальная цена')
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

    def __str__(self):
        return f'Заявка №{self.pk} от {self.client.username}'

    def clean(self):
        super().clean()
        errors = {}
        if self.client_id and self.client.user_type != 'client':
            errors['client'] = 'В поле клиента можно выбрать только пользователя типа "Клиент".'
        if self.agent_id and self.agent.user_type != 'employee':
            errors['agent'] = 'В поле агента можно выбрать только сотрудника.'
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            errors['min_price'] = 'Минимальная цена не может быть больше максимальной.'
        if self.min_area is not None and self.max_area is not None and self.min_area > self.max_area:
            errors['min_area'] = 'Минимальная площадь не может быть больше максимальной.'
        if (
            (self.property_type or '').strip()
            in {Property.PREMISES_OFFICE, Property.PREMISES_WAREHOUSE}
            and self.rooms_count is not None
        ):
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


class RequestPropertyMatch(models.Model):
    """Вариант объекта по заявке клиента."""
    request = models.ForeignKey(Request, on_delete=models.CASCADE,
                                    verbose_name='Заявка',
                                related_name='matches')
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                     verbose_name='Объект',
                                 related_name='request_matches')
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='proposed_matches',
                                  verbose_name='Агент',
                              limit_choices_to={'user_type_ref__code': 'employee'})
    agent_note = models.TextField(blank=True, null=True, verbose_name='Заметка агента')
    is_offered = models.BooleanField(default=True,
                                         verbose_name='Предложено клиенту',
                                     help_text='Предложено клиенту')
    is_rejected = models.BooleanField(default=False,
                                          verbose_name='Отклонено клиентом',
                                      help_text='Клиент отказался')
    is_confirmed = models.BooleanField(default=False,
                                           verbose_name='Подтверждено клиентом',
                                       help_text='Клиент подтвердил вариант')
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
            models.CheckConstraint(
                condition=~(models.Q(is_confirmed=True) & models.Q(is_rejected=True)),
                name='request_match_not_confirmed_and_rejected',
            ),
        ]

    def __str__(self):
        return f'Заявка №{self.request_id} ↔ объект №{self.property_id}'

    def clean(self):
        super().clean()
        errors = {}
        if self.is_confirmed and self.is_rejected:
            errors['is_confirmed'] = 'Вариант не может быть одновременно подтверждён и отклонён.'
        if self.confirmed_at and not self.is_confirmed:
            errors['confirmed_at'] = 'Дата подтверждения допускается только для подтверждённого варианта.'
        if errors:
            raise ValidationError(errors)

    @_property
    def state_code(self) -> str:
        if self.is_confirmed:
            return 'confirmed'
        if self.is_rejected:
            return 'rejected'
        if self.is_offered:
            return 'offered'
        return 'draft'


class Deal(models.Model):
    CONTRACT_STATUS_CHOICES = [
        ('not_requested', 'Не запрошен'),
        ('pending', 'В очереди'),
        ('processing', 'Формируется'),
        ('ready', 'Готов'),
        ('failed', 'Ошибка'),
    ]
    """Сделка по объекту и клиенту."""
    deal_number = models.CharField(max_length=50, unique=True, verbose_name='Номер сделки')
    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                     verbose_name='Объект',
                                 related_name='deals')
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_deals',
                                  verbose_name='Агент',
                              limit_choices_to={'user_type_ref__code': 'employee'})
    client = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='client_deals',
                                   verbose_name='Клиент',
                               limit_choices_to={'user_type_ref__code': 'client'})
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

    price_final = models.FloatField(validators=[MinValueValidator(0)], verbose_name='Итоговая цена')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                             blank=True, null=True,
                                                 verbose_name='Процент комиссии',
                                             validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    commission_amount = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)], verbose_name='Сумма комиссии')

    deal_date = models.DateField(verbose_name='Дата сделки')
    notes = models.TextField(blank=True, null=True, verbose_name='Примечания')

    contract_file = models.FileField(
        upload_to='contracts/%Y/%m/', blank=True, null=True,
        verbose_name='Файл договора',
    )
    contract_status_ref = models.ForeignKey(
        ContractStatus,
        on_delete=models.PROTECT,
        related_name='deals',
        verbose_name='Статус договора',
        default=1,
    )
    contract_error_message = models.TextField(blank=True, null=True, verbose_name='Ошибка договора')
    contract_requested_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата запроса договора')
    contract_processing_started_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата начала формирования договора')
    contract_generated_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата формирования договора')

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
        errors = {}
        if self.agent_id and self.agent.user_type != 'employee':
            errors['agent'] = 'Агентом сделки может быть только сотрудник.'
        if self.client_id and self.client.user_type != 'client':
            errors['client'] = 'Клиентом сделки может быть только пользователь типа "Клиент".'
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
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


class PropertyStatusHistory(models.Model):
    """История изменения статусов объектов."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                     verbose_name='Объект',
                                 related_name='status_history')
    old_status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        verbose_name='Старый статус',
        related_name='history_old_records',
        blank=True,
        null=True,
    )
    new_status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        verbose_name='Новый статус',
        related_name='history_new_records',
    )
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT,
                                       verbose_name='Изменил',
                                    related_name='status_changes')
    changed_at = models.DateTimeField(default=timezone.now, verbose_name='Дата изменения')

    class Meta:
        db_table = 'property_status_history'
        verbose_name = 'История статусов'
        verbose_name_plural = 'История статусов'
        ordering = ['-changed_at']
    QUERY_ALIASES = {
        'status': 'new_status',
        'status_id': 'new_status_id',
    }
    objects = AliasManager()

    def clean(self):
        super().clean()
        if self.changed_by_id and self.changed_by.user_type != 'employee':
            raise ValidationError({'changed_by': 'Статус объекта может менять только сотрудник.'})

    def __init__(self, *args, **kwargs):
        legacy_status = kwargs.pop('status', None)
        super().__init__(*args, **kwargs)
        if legacy_status is not None and not self.new_status_id:
            self.status = legacy_status

    @_property
    def status(self):
        return self.new_status

    @status.setter
    def status(self, value):
        self.new_status = value

    def save(self, *args, **kwargs):
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


class PropertyViewing(models.Model):
    """Запланированный просмотр объекта клиентом."""
    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                     verbose_name='Объект',
                                 related_name='viewings')
    client = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='client_viewings',
                                   verbose_name='Клиент',
                               limit_choices_to={'user_type_ref__code': 'client'})
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_viewings',
                                  verbose_name='Агент',
                              limit_choices_to={'user_type_ref__code': 'employee'})
    scheduled_date = models.DateTimeField(verbose_name='Дата просмотра')
    notes = models.TextField(blank=True, null=True, verbose_name='Примечания')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        db_table = 'property_viewings'
        verbose_name = 'Просмотр объекта'
        verbose_name_plural = 'Просмотры объектов'
        ordering = ['-scheduled_date']

    def clean(self):
        super().clean()
        errors = {}
        if self.client_id and self.client.user_type != 'client':
            errors['client'] = 'В просмотре клиентом может быть только пользователь типа "Клиент".'
        if self.agent_id and self.agent.user_type != 'employee':
            errors['agent'] = 'Агентом просмотра может быть только сотрудник.'
        if errors:
            raise ValidationError(errors)


class Task(models.Model):
    """Задача сотрудника."""
    PRIORITY_CHOICES = [
        ('low',    'Низкий'),
        ('normal', 'Обычный'),
        ('high',   'Высокий'),
    ]

    TASK_TYPE_CHOICES = [
        ('contact_client', 'Связаться с клиентом'),
        ('property_search', 'Подбор объектов'),
        ('showing', 'Показ объекта'),
        ('documents', 'Подготовка документов'),
        ('call', 'Звонок'),
        ('other', 'Прочее'),
    ]

    TERMINAL_STATUS_CODES = ('done', 'cancelled')

    title = models.CharField(max_length=255, verbose_name='Название')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    priority_ref = models.ForeignKey(
        TaskPriority,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name='Приоритет',
        default=2,
    )
    task_type_ref = models.ForeignKey(
        TaskType,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name='Тип задач',
        default=6,
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

    client = models.ForeignKey(User, on_delete=models.SET_NULL,
                               blank=True, null=True,
                               related_name='client_tasks',
                                   verbose_name='Клиент',
                               limit_choices_to={'user_type_ref__code': 'client'})
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
    # История шагов из TaskWorkflow.
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
    }
    objects = AliasManager()

    def __str__(self):
        return self.title

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
        errors = {}
        if self.assignee_id and self.assignee.user_type != 'employee':
            errors['assignee'] = 'Исполнителем задачи может быть только сотрудник.'
        if self.created_by_id and self.created_by.user_type != 'employee':
            errors['created_by'] = 'Создателем задачи должен быть сотрудник.'
        if self.client_id and self.client.user_type != 'client':
            errors['client'] = 'В поле клиента можно выбрать только пользователя типа "Клиент".'
        if self.completed_at and self.status_id and self.status.code not in self.TERMINAL_STATUS_CODES:
            errors['completed_at'] = 'Дата завершения допускается только для финального статуса задачи.'
        if errors:
            raise ValidationError(errors)

    @_property
    def is_completed(self):
        """Проверяет, завершена ли задача."""
        return (self.status_id is not None
                and self.status.code in self.TERMINAL_STATUS_CODES)

    @_property
    def is_terminal(self):
        return self.is_completed

    @_property
    def task_type_display(self):
        """Человекочитаемое название типа задачи."""
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
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


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
        return f'{self.subject} → {self.recipient.email}'

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

    ENTITY_TYPE_CHOICES = [
        ('property', 'Объект'),
        ('request', 'Заявка'),
        ('task', 'Задача'),
        ('deal', 'Сделка'),
    ]

    entity_type = models.CharField(max_length=32, choices=ENTITY_TYPE_CHOICES, db_index=True, verbose_name='Код типа сущности')
    entity_id = models.PositiveIntegerField(db_index=True, verbose_name='Идентификатор сущности')
    action_code = models.CharField(max_length=64, db_index=True, verbose_name='Код действия')
    action_label = models.CharField(max_length=255, verbose_name='Действие')
    message = models.TextField(blank=True, default='', verbose_name='Сообщение')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Метаданные')

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        verbose_name='Инициатор',
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        verbose_name='Объект',
    )
    request = models.ForeignKey(
        Request,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        verbose_name='Заявка',
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        verbose_name='Задача',
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        verbose_name='Сделка',
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Дата создания')

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Запись журнала'
        verbose_name_plural = 'Журнал действий'
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(entity_type__in=['property', 'request', 'task', 'deal']),
                name='audit_log_entity_type_valid',
            ),
        ]

    def __str__(self):
        return f'{self.get_entity_type_display()} #{self.entity_id}: {self.action_label}'


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
