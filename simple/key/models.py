"""
ORM-модели приложения `key`.

Полностью повторяют 3НФ-схему PostgreSQL из проектной документации:
справочники, адресная иерархия (совместимая с ФИАС), пользователи,
профили, объекты недвижимости, заявки, сделки, история статусов, просмотры.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


# ====== СПРАВОЧНИКИ =========================================================

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


class UserRole(models.Model):
    """Роль сотрудника в системе."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'user_roles'
        verbose_name = 'Роль пользователя'
        verbose_name_plural = 'Роли пользователей'

    def __str__(self):
        return self.name


# ====== АДРЕСА (иерархия, совместимая с ФИАС) ==============================

class City(models.Model):
    """Город / населённый пункт (объект ФИАС уровня 4)."""
    name = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, null=True)
    fias_id = models.UUIDField(blank=True, null=True, db_index=True,
                               help_text='Object GUID из ФИАС')

    class Meta:
        db_table = 'cities'
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        indexes = [models.Index(fields=['name'])]

    def __str__(self):
        return f'{self.name}, {self.region}' if self.region else self.name


class Street(models.Model):
    """Улица (объект ФИАС уровня 7)."""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='streets')
    name = models.CharField(max_length=150)
    street_type = models.CharField(max_length=20, blank=True, null=True)
    fias_id = models.UUIDField(blank=True, null=True, db_index=True)

    class Meta:
        db_table = 'streets'
        verbose_name = 'Улица'
        verbose_name_plural = 'Улицы'

    def __str__(self):
        return f'{self.street_type or ""} {self.name}'.strip()


class House(models.Model):
    """Дом (объект ФИАС уровня 8)."""
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='houses')
    house_number = models.CharField(max_length=20)
    building = models.CharField(max_length=10, blank=True, null=True)
    structure = models.CharField(max_length=10, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    fias_id = models.UUIDField(blank=True, null=True, db_index=True)

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
    """Полный адрес (дом + квартира/этаж)."""
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name='addresses')
    apartment_number = models.CharField(max_length=20, blank=True, null=True)
    entrance = models.IntegerField(blank=True, null=True)
    floor = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'addresses'
        verbose_name = 'Адрес'
        verbose_name_plural = 'Адреса'
        constraints = [
            models.UniqueConstraint(fields=['house', 'apartment_number'],
                                    name='unique_address'),
        ]

    def __str__(self):
        base = f'{self.house.street.city}, {self.house.street}, {self.house}'
        if self.apartment_number:
            base += f', кв. {self.apartment_number}'
        return base


# ====== ПОЛЬЗОВАТЕЛИ ========================================================

class UserManager(BaseUserManager):
    """Менеджер кастомной модели пользователя."""

    def create_user(self, username, email, password=None, **extra):
        if not username:
            raise ValueError('Username обязателен')
        if not email:
            raise ValueError('Email обязателен')
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
    """Единая таблица пользователей (сотрудники и клиенты)."""
    USER_TYPE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('client', 'Клиент'),
    ]

    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)

    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
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

    def __str__(self):
        return f'{self.username} ({self.get_user_type_display()})'


# ====== ПРОФИЛИ =============================================================

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


class ClientProfile(models.Model):
    """Профиль клиента."""
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name='client_profile')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)

    passport_series = models.CharField(max_length=4, blank=True, null=True)
    passport_number = models.CharField(max_length=6, blank=True, null=True)
    passport_issued_by = models.CharField(max_length=255, blank=True, null=True)
    passport_issued_date = models.DateField(blank=True, null=True)
    passport_code = models.CharField(max_length=7, blank=True, null=True)

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

    def __str__(self):
        return f'{self.last_name} {self.first_name}'


# ====== ОБЪЕКТЫ НЕДВИЖИМОСТИ ===============================================

class Property(models.Model):
    """Объект недвижимости."""
    title = models.CharField(max_length=255, blank=True, null=True)
    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       related_name='properties')
    status = models.ForeignKey(PropertyStatus, on_delete=models.PROTECT,
                               related_name='properties', default=1)
    address = models.ForeignKey(Address, on_delete=models.PROTECT,
                                related_name='properties')

    coordinates_lat = models.DecimalField(max_digits=10, decimal_places=8,
                                          blank=True, null=True)
    coordinates_lon = models.DecimalField(max_digits=11, decimal_places=8,
                                          blank=True, null=True)

    price = models.FloatField()
    price_per_sqm = models.FloatField(blank=True, null=True)

    area_total = models.DecimalField(max_digits=8, decimal_places=2,
                                     blank=True, null=True)
    area_living = models.DecimalField(max_digits=8, decimal_places=2,
                                      blank=True, null=True)
    area_kitchen = models.DecimalField(max_digits=8, decimal_places=2,
                                       blank=True, null=True)

    rooms_count = models.IntegerField(blank=True, null=True)
    floor_number = models.IntegerField(blank=True, null=True)
    total_floors = models.IntegerField(blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'properties'
        verbose_name = 'Объект недвижимости'
        verbose_name_plural = 'Объекты недвижимости'
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f'Объект #{self.pk}'


class PropertyFeature(models.Model):
    """Характеристика объекта (балкон, ремонт, парковка и т. п.)."""
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'property_features'
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'

    def __str__(self):
        return self.name


class PropertyFeatureValue(models.Model):
    """Значение характеристики для конкретного объекта."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 related_name='feature_values')
    feature = models.ForeignKey(PropertyFeature, on_delete=models.CASCADE,
                                related_name='values')
    value = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'property_feature_values'
        verbose_name = 'Значение характеристики'
        verbose_name_plural = 'Значения характеристик'
        unique_together = [('property', 'feature')]

    def __str__(self):
        return f'{self.feature.name}: {self.value}'


class PropertyPhoto(models.Model):
    """Фотография объекта."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 related_name='photos')
    url = models.TextField()
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'property_photos'
        verbose_name = 'Фото объекта'
        verbose_name_plural = 'Фото объектов'


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


# ====== ЗАЯВКИ И СДЕЛКИ ====================================================

class Request(models.Model):
    """Заявка клиента на подбор недвижимости."""
    client = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='client_requests',
                               limit_choices_to={'user_type': 'client'})
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_requests',
                              limit_choices_to={'user_type': 'employee'})

    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       related_name='requests')
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT,
                               related_name='requests', default=1)

    property_type = models.CharField(max_length=50, blank=True, null=True)
    min_price = models.FloatField(blank=True, null=True)
    max_price = models.FloatField(blank=True, null=True)
    min_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True)
    max_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True)
    rooms_count = models.IntegerField(blank=True, null=True)

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

    def __str__(self):
        return f'Заявка #{self.pk} от {self.client.username}'


class Deal(models.Model):
    """Сделка (продажа/аренда)."""
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

    price_final = models.FloatField()
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                             blank=True, null=True)
    commission_amount = models.FloatField(blank=True, null=True)

    deal_date = models.DateField()

    class Meta:
        db_table = 'deals'
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'
        ordering = ['-deal_date']

    def __str__(self):
        return f'Сделка {self.deal_number}'


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
