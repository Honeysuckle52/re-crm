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

class OperationType(models.Model):
    """Тип операции с недвижимостью (продажа / аренда)."""
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)

    class Meta:
        db_table = 'operation_types'
        verbose_name = 'Тип операции'
        verbose_name_plural = 'Типы операций'

    def __str__(self):
        return self.name


class PropertyStatus(models.Model):
    """Статус объекта недвижимости."""
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)

    class Meta:
        db_table = 'property_statuses'
        verbose_name = 'Статус объекта'
        verbose_name_plural = 'Статусы объектов'

    def __str__(self):
        return self.name


class RequestStatus(models.Model):
    """Статус заявки клиента."""
    code = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=50)

    class Meta:
        db_table = 'request_statuses'
        verbose_name = 'Статус заявки'
        verbose_name_plural = 'Статусы заявок'

    def __str__(self):
        return self.name


class DealStatus(models.Model):
    """Статус сделки — стадия воронки продаж."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    order = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        db_table = 'deal_statuses'
        verbose_name = 'Статус сделки'
        verbose_name_plural = 'Статусы сделок'
        ordering = ['order']

    def __str__(self):
        return self.name


class TaskStatus(models.Model):
    """Статус задачи сотрудника."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    order = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        db_table = 'task_statuses'
        verbose_name = 'Статус задачи'
        verbose_name_plural = 'Статусы задач'
        ordering = ['order']

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """Роль сотрудника в системе (администратор / менеджер / агент)."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    max_active_tasks = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    max_in_progress_tasks = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    max_active_requests = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
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
    name = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, null=True)
    external_id = models.UUIDField(
        blank=True, null=True, db_index=True,
        help_text='Внешний идентификатор адресного реестра (из DaData)',
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
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='streets')
    name = models.CharField(max_length=150)
    street_type = models.CharField(max_length=20, blank=True, null=True)
    external_id = models.UUIDField(blank=True, null=True, db_index=True)

    class Meta:
        db_table = 'streets'
        verbose_name = 'Улица'
        verbose_name_plural = 'Улицы'

    def __str__(self):
        return f'{self.street_type or ""} {self.name}'.strip()


class House(models.Model):
    """Дом / строение."""
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='houses')
    house_number = models.CharField(max_length=20)
    building = models.CharField(max_length=10, blank=True, null=True)
    structure = models.CharField(max_length=10, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    external_id = models.UUIDField(blank=True, null=True, db_index=True)

    class Meta:
        db_table = 'houses'
        verbose_name = 'Дом'
        verbose_name_plural = 'Дома'

    def __str__(self):
        parts = [f'д. {self.house_number}']
        if self.building:
            parts.append(f'к. {self.building}')
        if self.structure:
            parts.append(f'стр. {self.structure}')
        return ' '.join(parts)


class Address(models.Model):
    """Полный адрес: дом + квартира/этаж/подъезд."""
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name='addresses')
    apartment_number = models.CharField(max_length=20, blank=True, null=True)
    entrance = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )
    floor = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(-5), MaxValueValidator(300)],
    )

    class Meta:
        db_table = 'addresses'
        verbose_name = 'Адрес'
        verbose_name_plural = 'Адреса'
        constraints = [
            models.UniqueConstraint(fields=['house', 'apartment_number'],
                                    name='unique_address'),
            models.CheckConstraint(
                condition=(
                    models.Q(entrance__isnull=True)
                    | (models.Q(entrance__gte=1) & models.Q(entrance__lte=99))
                ),
                name='address_entrance_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(floor__isnull=True)
                    | (models.Q(floor__gte=-5) & models.Q(floor__lte=300))
                ),
                name='address_floor_range',
            ),
        ]

    def __str__(self):
        base = f'{self.house.street.city}, {self.house.street}, {self.house}'
        if self.apartment_number:
            base += f', кв. {self.apartment_number}'
        return base

class UserManager(BaseUserManager):
    """Менеджер кастомной модели пользователя."""

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
    )
    email = models.EmailField(max_length=255, unique=True)
    phone = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        validators=[phone_validator],
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES,
                                 default='client')
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL,
                             blank=True, null=True, related_name='users')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)

    last_login = models.DateTimeField(blank=True, null=True)
    last_ip = models.GenericIPAddressField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user_type__in=['employee', 'client']),
                name='user_type_valid',
            ),
        ]

    def __str__(self):
        return f'{self.username} ({self.get_user_type_display()})'

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
    def is_admin_role(self) -> bool:
        return self.is_superuser or self.role_code == 'admin'

    @property
    def is_manager_role(self) -> bool:
        return self.role_code == 'manager'

    @property
    def is_admin_or_manager(self) -> bool:
        return self.is_admin_role or self.is_manager_role

    @property
    def is_employee(self) -> bool:
        return self.user_type == 'employee'

    @property
    def is_client(self) -> bool:
        return self.user_type == 'client'

class EmployeeProfile(models.Model):
    """Профиль сотрудника."""
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name='employee_profile')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    hire_date = models.DateField(blank=True, null=True)
    internal_phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_profiles'
        verbose_name = 'Профиль сотрудника'
        verbose_name_plural = 'Профили сотрудников'

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    def clean(self):
        super().clean()
        if self.user_id and self.user.user_type != 'employee':
            raise ValidationError({'user': 'Профиль сотрудника можно привязать только к пользователю типа "Сотрудник".'})


class ClientProfile(models.Model):
    """Профиль клиента."""
    CLIENT_KIND_INDIVIDUAL = 'individual'
    CLIENT_KIND_COMPANY = 'company'
    CLIENT_KIND_CHOICES = [
        (CLIENT_KIND_INDIVIDUAL, 'Физическое лицо'),
        (CLIENT_KIND_COMPANY, 'Юридическое лицо'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name='client_profile')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    client_kind = models.CharField(
        max_length=20,
        choices=CLIENT_KIND_CHOICES,
        default=CLIENT_KIND_INDIVIDUAL,
    )

    registration_address = models.TextField(blank=True, null=True)
    actual_address = models.TextField(blank=True, null=True)

    preferred_contact_method = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_profiles'
        verbose_name = 'Профиль клиента'
        verbose_name_plural = 'Профили клиентов'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(client_kind__in=['individual', 'company']),
                name='client_profile_kind_valid',
            ),
        ]

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    def clean(self):
        super().clean()
        if self.user_id and self.user.user_type != 'client':
            raise ValidationError({'user': 'Профиль клиента можно привязать только к пользователю типа "Клиент".'})


class ClientIndividualDetails(models.Model):
    """Паспортные данные клиента-физлица."""
    profile = models.OneToOneField(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='individual_details',
    )
    passport_series = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        validators=[passport_series_validator],
    )
    passport_number = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        validators=[passport_number_validator],
    )
    passport_issued_by = models.CharField(max_length=255, blank=True, null=True)
    passport_issued_date = models.DateField(blank=True, null=True)
    passport_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        validators=[passport_code_validator],
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

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
    )
    company_inn = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        db_index=True,
        validators=[company_inn_validator],
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

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
        (PREMISES_APARTMENT, 'Apartment'),
        (PREMISES_HOUSE, 'House'),
        (PREMISES_OFFICE, 'Office'),
        (PREMISES_WAREHOUSE, 'Warehouse'),
    ]

    """Объект недвижимости."""
    title = models.CharField(max_length=255, blank=True, null=True)
    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       related_name='properties')
    status = models.ForeignKey(PropertyStatus, on_delete=models.PROTECT,
                               related_name='properties', default=1)
    address = models.ForeignKey(Address, on_delete=models.PROTECT,
                                related_name='properties')

    coordinates_lat = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('-90')), MaxValueValidator(Decimal('90'))],
    )
    coordinates_lon = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('-180')), MaxValueValidator(Decimal('180'))],
    )
    twogis_org_id = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    twogis_name = models.CharField(max_length=255, blank=True, null=True)
    twogis_address_full = models.TextField(blank=True, null=True)
    twogis_rubric = models.CharField(max_length=255, blank=True, null=True)
    twogis_synced_at = models.DateTimeField(blank=True, null=True)
    premises_type = models.CharField(
        max_length=20,
        choices=PREMISES_TYPE_CHOICES,
        default=PREMISES_APARTMENT,
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='owned_properties',
        limit_choices_to={'user_type': 'client'},
        blank=True,
        null=True,
    )

    price = models.FloatField(validators=[MinValueValidator(0)])
    price_per_sqm = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])

    area_total = models.DecimalField(max_digits=8, decimal_places=2,
                                     blank=True, null=True,
                                     validators=[MinValueValidator(Decimal('0.01'))])

    rooms_count = models.IntegerField(blank=True, null=True,
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])
    floor_number = models.IntegerField(blank=True, null=True,
                                       validators=[MinValueValidator(-5), MaxValueValidator(300)])
    total_floors = models.IntegerField(blank=True, null=True,
                                       validators=[MinValueValidator(0), MaxValueValidator(300)])

    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'properties'
        verbose_name = 'Объект недвижимости'
        verbose_name_plural = 'Объекты недвижимости'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='property_price_non_negative'),
            models.CheckConstraint(
                condition=models.Q(price_per_sqm__isnull=True) | models.Q(price_per_sqm__gte=0),
                name='property_price_per_sqm_non_negative',
            ),
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
                condition=models.Q(premises_type__in=['apartment', 'house', 'office', 'warehouse']),
                name='property_premises_type_valid',
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

    def __str__(self):
        return self.title or f'Объект №{self.pk}'

    def clean(self):
        super().clean()
        errors = {}
        if self.price is not None and self.price < 0:
            errors['price'] = 'Цена не может быть отрицательной.'
        if self.price_per_sqm is not None and self.price_per_sqm < 0:
            errors['price_per_sqm'] = 'Цена за м² не может быть отрицательной.'
        if self.area_total is not None and self.area_total <= 0:
            errors['area_total'] = 'Площадь должна быть больше нуля.'
        if self.rooms_count is not None and self.rooms_count < 0:
            errors['rooms_count'] = 'Количество комнат не может быть отрицательным.'
        if (
            self.floor_number is not None
            and self.total_floors is not None
            and self.floor_number > self.total_floors
        ):
            errors['floor_number'] = 'Этаж объекта не может быть выше общего количества этажей.'
        if self.owner_id and self.owner.user_type != 'client':
            errors['owner'] = 'Owner must be a client user.'
        if errors:
            raise ValidationError(errors)



class PropertyPhoto(models.Model):
    """Фотография объекта."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 related_name='photos')
    image = models.ImageField(upload_to='%Y/%m/',
                              blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True, null=True)
    is_cover = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(default=timezone.now)

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
                                 related_name='documents')
    document_name = models.CharField(max_length=255)
    file_url = models.TextField()
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    blank=True, null=True,
                                    related_name='verified_documents')
    verified_at = models.DateTimeField(blank=True, null=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

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
                               limit_choices_to={'user_type': 'client'})
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_requests',
                              blank=True, null=True,
                              limit_choices_to={'user_type': 'employee'})
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 related_name='direct_requests',
                                 blank=True, null=True)

    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       related_name='requests')
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT,
                               related_name='requests', default=1)
    property_type = models.CharField(max_length=50, blank=True, null=True)
    min_price = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    max_price = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    min_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True,
                                   validators=[MinValueValidator(Decimal('0.01'))])
    max_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True,
                                   validators=[MinValueValidator(Decimal('0.01'))])
    rooms_count = models.IntegerField(blank=True, null=True,
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])

    address_preferences = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(blank=True, null=True)

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
                                related_name='matches')
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 related_name='request_matches')
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='proposed_matches',
                              limit_choices_to={'user_type': 'employee'})
    agent_note = models.TextField(blank=True, null=True)
    is_offered = models.BooleanField(default=True,
                                     help_text='Предложено клиенту')
    is_rejected = models.BooleanField(default=False,
                                      help_text='Клиент отказался')
    is_confirmed = models.BooleanField(default=False,
                                       help_text='Клиент подтвердил вариант')
    confirmed_at = models.DateTimeField(blank=True, null=True)
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='confirmed_request_matches',
        limit_choices_to={'user_type': 'employee'},
    )
    created_at = models.DateTimeField(default=timezone.now)

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
    deal_number = models.CharField(max_length=50, unique=True)
    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                 related_name='deals')
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_deals',
                              limit_choices_to={'user_type': 'employee'})
    client = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='client_deals',
                               limit_choices_to={'user_type': 'client'})
    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       related_name='deals')
    status = models.ForeignKey(DealStatus, on_delete=models.PROTECT,
                               related_name='deals',
                               blank=True, null=True)

    request = models.OneToOneField(
        Request, on_delete=models.SET_NULL,
        related_name='deal', blank=True, null=True,
    )

    price_final = models.FloatField(validators=[MinValueValidator(0)])
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                             blank=True, null=True,
                                             validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    commission_amount = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])

    deal_date = models.DateField()
    notes = models.TextField(blank=True, null=True)

    contract_file = models.FileField(
        upload_to='contracts/%Y/%m/', blank=True, null=True,
    )
    contract_status = models.CharField(
        max_length=20,
        choices=CONTRACT_STATUS_CHOICES,
        default='not_requested',
        db_index=True,
    )
    contract_error_message = models.TextField(blank=True, null=True)
    contract_requested_at = models.DateTimeField(blank=True, null=True)
    contract_processing_started_at = models.DateTimeField(blank=True, null=True)
    contract_generated_at = models.DateTimeField(blank=True, null=True)

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

    def __str__(self):
        return f'Сделка {self.deal_number}'

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


class PropertyStatusHistory(models.Model):
    """История изменения статусов объектов."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 related_name='status_history')
    status = models.ForeignKey(PropertyStatus, on_delete=models.PROTECT,
                               related_name='history_records')
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT,
                                   related_name='status_changes')
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'property_status_history'
        verbose_name = 'История статусов'
        verbose_name_plural = 'История статусов'
        ordering = ['-changed_at']

    def clean(self):
        super().clean()
        if self.changed_by_id and self.changed_by.user_type != 'employee':
            raise ValidationError({'changed_by': 'Статус объекта может менять только сотрудник.'})


class PropertyViewing(models.Model):
    """Запланированный просмотр объекта клиентом."""
    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                 related_name='viewings')
    client = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='client_viewings',
                               limit_choices_to={'user_type': 'client'})
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_viewings',
                              limit_choices_to={'user_type': 'employee'})
    scheduled_date = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

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

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES,
                                default='normal')
    task_type = models.CharField(max_length=30, choices=TASK_TYPE_CHOICES,
                                 default='other', db_index=True)
    status = models.ForeignKey(TaskStatus, on_delete=models.PROTECT,
                               related_name='tasks')

    assignee = models.ForeignKey(User, on_delete=models.PROTECT,
                                 related_name='assigned_tasks',
                                 limit_choices_to={'user_type': 'employee'})
    created_by = models.ForeignKey(User, on_delete=models.PROTECT,
                                   related_name='created_tasks')

    client = models.ForeignKey(User, on_delete=models.SET_NULL,
                               blank=True, null=True,
                               related_name='client_tasks',
                               limit_choices_to={'user_type': 'client'})
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='tasks')
    request = models.ForeignKey(Request, on_delete=models.SET_NULL,
                                blank=True, null=True, related_name='tasks')
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL,
                             blank=True, null=True, related_name='tasks')

    due_date = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    result = models.TextField(blank=True, null=True,
                              help_text='Результат выполнения задачи')
    # История шагов из TaskWorkflow.
    steps_log = models.JSONField(
        default=list, blank=True,
        help_text='Журнал этапов выполнения (список объектов).',
    )
    is_auto_closed = models.BooleanField(default=False,
                                         help_text='Закрыта автоматически системой')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks'
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(priority__in=['low', 'normal', 'high']),
                name='task_priority_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(task_type__in=[
                    'contact_client',
                    'property_search',
                    'showing',
                    'documents',
                    'call',
                    'other',
                ]),
                name='task_type_valid',
            ),
        ]

    def __str__(self):
        return self.title

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
        return dict(self.TASK_TYPE_CHOICES).get(self.task_type, self.task_type)


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
    )
    sender = models.ForeignKey(User, on_delete=models.SET_NULL,
                               blank=True, null=True,
                               related_name='sent_emails',
                               limit_choices_to={'user_type': 'employee'})
    subject = models.CharField(max_length=255)
    body = models.TextField()
    html_body = models.TextField(blank=True, default='')
    trigger_code = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='pending', db_index=True)

    task = models.ForeignKey(Task, on_delete=models.SET_NULL,
                             blank=True, null=True, related_name='emails')
    request = models.ForeignKey(Request, on_delete=models.SET_NULL,
                                blank=True, null=True, related_name='emails')
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='emails')

    error_message = models.TextField(blank=True, null=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

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

    entity_type = models.CharField(max_length=32, choices=ENTITY_TYPE_CHOICES, db_index=True)
    entity_id = models.PositiveIntegerField(db_index=True)
    action_code = models.CharField(max_length=64, db_index=True)
    action_label = models.CharField(max_length=255)
    message = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
    )
    request = models.ForeignKey(
        Request,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

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

    filename = models.CharField(max_length=255)
    file = models.FileField(
        storage=database_backup_storage,
        upload_to='database_backups/%Y/%m/',
    )
    size_bytes = models.PositiveBigIntegerField(default=0)
    database_name = models.CharField(max_length=255)
    engine_label = models.CharField(max_length=120)
    tool_label = models.CharField(max_length=120, blank=True, default='')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='database_backups',
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'database_backups'
        verbose_name = 'Резервная копия БД'
        verbose_name_plural = 'Резервные копии БД'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.filename
