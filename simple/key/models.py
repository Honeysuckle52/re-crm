"""
ORM-модели приложения ``key``.

Соответствуют 3НФ-схеме БД учётной системы агентства недвижимости:
справочники, адресная иерархия, пользователи, профили, объекты, заявки,
сделки, история статусов, просмотры, задачи сотрудников.

Адресные идентификаторы хранятся в поле ``external_id`` — это GUID из
реестра, который возвращает сервис подсказок DaData.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

# Псевдоним встроенного декоратора ``property``.
# В модели ``Task`` есть поле с именем ``property`` (FK на Property),
# которое внутри тела класса затеняет встроенный ``property``.
# Чтобы ниже можно было объявлять вычисляемые атрибуты через ``@_property``
# без конфликта имён, сохраняем ссылку на встроенный декоратор здесь.
_property = property


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


class DealStatus(models.Model):
    """Статус сделки — стадия воронки продаж."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    order = models.PositiveSmallIntegerField(default=0)

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
    order = models.PositiveSmallIntegerField(default=0)

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

    class Meta:
        db_table = 'user_roles'
        verbose_name = 'Роль пользователя'
        verbose_name_plural = 'Роли пользователей'

    def __str__(self):
        return self.name


# ====== АДРЕСА (иерархия) ==================================================

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
    """
    Единая таблица пользователей: сотрудники и клиенты.

    Тип пользователя и роль назначает администратор/менеджер — при
    самостоятельной регистрации всегда создаётся клиент без роли.
    """
    USER_TYPE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('client', 'Клиент'),
    ]

    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)

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

    def __str__(self):
        return f'{self.username} ({self.get_user_type_display()})'

    # --- утилиты прав доступа ------------------------------------------

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
        return self.title or f'Объект №{self.pk}'


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
    """
    Фотография объекта.

    Изображение загружает сотрудник агентства — DaData возвращает только
    адресные данные, а визуальный контент заполняется вручную. Допустимы
    оба варианта: загрузка файла (``image``) или внешний URL (``url``).

    Ранее файлы складывались в ``properties/%Y/%m/``. Теперь путь упрощён
    до ``%Y/%m/`` — ровно там, где лежат демо-картинки из
    ``seed_demo`` (``media/2026/04/1.jpg`` и т. д.). Старые файлы в
    ``media/properties/...`` можно либо удалить вручную, либо оставить —
    они останутся валидными ссылками у ранее созданных записей.
    """
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 related_name='photos')
    image = models.ImageField(upload_to='%Y/%m/',
                              blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True, null=True)
    # Обложка — первое фото, которое показывается на карточке.
    is_cover = models.BooleanField(default=False)
    # «Мягкое» скрытие. Позволяет сотруднику исключить фото из выдачи
    # клиенту, не удаляя его физически — для ручного управления альбомом.
    is_hidden = models.BooleanField(default=False)
    # Ручной порядок сортировки. 0 — самый верх, дальше по возрастанию.
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'property_photos'
        verbose_name = 'Фото объекта'
        verbose_name_plural = 'Фото объектов'
        ordering = ['-is_cover', 'order', '-uploaded_at']


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


# ====== ЗАЯВКИ, СДЕЛКИ, ПРОСМОТРЫ, ЗАДАЧИ ==================================

class Request(models.Model):
    """
    Заявка клиента на подбор/покупку/аренду недвижимости.

    Два сценария подачи:
      * «быстрая заявка» с карточки объекта — заполняется поле ``property``;
      * «заявка на подбор» в личном кабинете — указываются только критерии.
    Дополнительно агент может предлагать клиенту варианты через
    :class:`RequestPropertyMatch`.
    """
    client = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='client_requests',
                               limit_choices_to={'user_type': 'client'})
    # Агент назначается сотрудником после подачи заявки клиентом,
    # поэтому поле опциональное — до «взятия в работу» агента нет.
    agent = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='agent_requests',
                              blank=True, null=True,
                              limit_choices_to={'user_type': 'employee'})
    # Конкретный объект, привязанный к заявке (если клиент нажал
    # «Оставить заявку» на странице конкретной квартиры/дома).
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 related_name='direct_requests',
                                 blank=True, null=True)

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
        return f'Заявка №{self.pk} от {self.client.username}'


class RequestPropertyMatch(models.Model):
    """
    Вариант объекта, предложенный агентом по заявке клиента.

    Позволяет вести «подборку» — несколько объектов, которые агент
    отправил клиенту на рассмотрение. Клиент не может редактировать
    эту таблицу, но видит её в деталях своей заявки.
    """
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
    created_at = models.DateTimeField(default=timezone.now)

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
        return f'Заявка №{self.request_id} ↔ объект №{self.property_id}'


class Deal(models.Model):
    """Сделка (продажа / аренда) — воронка продаж."""
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

    price_final = models.FloatField()
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                             blank=True, null=True)
    commission_amount = models.FloatField(blank=True, null=True)

    deal_date = models.DateField()
    notes = models.TextField(blank=True, null=True)

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


class Task(models.Model):
    """
    Задача сотрудника (звонок, показ, подготовка документов и т. п.).

    Универсальная CRM-сущность: задача может быть связана с клиентом,
    объектом, заявкой или сделкой — любой из этих связей достаточно.
    """
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

    # Коды статусов, при которых задача считается завершённой
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
    is_auto_closed = models.BooleanField(default=False,
                                         help_text='Закрыта автоматически системой')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks'
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    # Используем @_property (ссылка на builtins.property),
    # т.к. поле ``property = models.ForeignKey(...)`` выше в теле класса
    # затенило встроенное имя ``property``.
    @_property
    def is_completed(self):
        """Проверяет, завершена ли задача."""
        return (self.status_id is not None
                and self.status.code in self.TERMINAL_STATUS_CODES)

    @_property
    def task_type_display(self):
        """Человекочитаемое название типа задачи."""
        return dict(self.TASK_TYPE_CHOICES).get(self.task_type, self.task_type)


class OutgoingEmail(models.Model):
    """
    Очередь исходящих писем клиентам.

    Используется для автоматических уведомлений (например, при
    подтверждении варианта подборки) и ручной отправки из CRM.
    Статус отслеживается для повторных попыток и логирования.
    """
    STATUS_CHOICES = [
        ('pending', 'Ожидает отправки'),
        ('sent', 'Отправлено'),
        ('failed', 'Ошибка отправки'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='outgoing_emails',
                                  limit_choices_to={'user_type': 'client'})
    sender = models.ForeignKey(User, on_delete=models.SET_NULL,
                               blank=True, null=True,
                               related_name='sent_emails',
                               limit_choices_to={'user_type': 'employee'})
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='pending', db_index=True)

    # Связи с бизнес-объектами (опциональные)
    task = models.ForeignKey(Task, on_delete=models.SET_NULL,
                             blank=True, null=True, related_name='emails')
    request = models.ForeignKey(Request, on_delete=models.SET_NULL,
                                blank=True, null=True, related_name='emails')
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='emails')

    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'outgoing_emails'
        verbose_name = 'Исходящее письмо'
        verbose_name_plural = 'Исходящие письма'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subject} → {self.recipient.email}'
