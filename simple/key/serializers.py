"""Сериализаторы DRF приложения ``key``."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from . import models

User = get_user_model()


# ---------- Справочники ----------------------------------------------------

class OperationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OperationType
        fields = ['id', 'code', 'name']


class PropertyStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PropertyStatus
        fields = ['id', 'code', 'name']


class RequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RequestStatus
        fields = ['id', 'code', 'name']


class DealStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DealStatus
        fields = ['id', 'code', 'name', 'order']


class TaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TaskStatus
        fields = ['id', 'code', 'name', 'order']


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserRole
        fields = ['id', 'code', 'name', 'description']


# ---------- Адреса ---------------------------------------------------------

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.City
        fields = ['id', 'name', 'region', 'external_id']


class StreetSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = models.Street
        fields = ['id', 'city', 'city_name', 'name', 'street_type', 'external_id']


class HouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.House
        fields = ['id', 'street', 'house_number', 'building',
                  'structure', 'postal_code', 'external_id']


class AddressSerializer(serializers.ModelSerializer):
    full_address = serializers.SerializerMethodField()

    class Meta:
        model = models.Address
        fields = ['id', 'house', 'apartment_number', 'entrance',
                  'floor', 'full_address']

    def get_full_address(self, obj) -> str:
        return str(obj)


# ---------- Пользователи и профили ----------------------------------------

class UserSerializer(serializers.ModelSerializer):
    """Полное представление пользователя.

    Дополнительно отдаём ``is_superuser``/``is_staff`` и вычисляемый
    флаг ``is_admin`` — они нужны фронтенду, чтобы показывать админ-UI
    суперюзеру даже без явно назначенной роли «admin» в справочнике.
    """
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_code = serializers.CharField(source='role.code', read_only=True)
    user_type_display = serializers.CharField(source='get_user_type_display',
                                              read_only=True)
    is_admin = serializers.BooleanField(source='is_admin_role', read_only=True)
    is_manager = serializers.BooleanField(source='is_admin_or_manager',
                                          read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone',
                  'user_type', 'user_type_display',
                  'role', 'role_name', 'role_code',
                  'is_active', 'is_staff', 'is_superuser',
                  'is_admin', 'is_manager',
                  'is_email_verified', 'is_phone_verified',
                  'created_at']
        read_only_fields = ['id', 'created_at', 'is_staff', 'is_superuser',
                            'is_admin', 'is_manager']


class RegisterSerializer(serializers.ModelSerializer):
    """
    Самостоятельная регистрация.

    Пользователь НЕ выбирает ни ``user_type``, ни ``role`` — оба поля
    заполняются автоматически: тип — клиент, роль — отсутствует.
    Назначение сотрудника и роли делает администратор или менеджер
    через эндпоинт ``/api/users/{id}/assign_role/``.
    """
    password = serializers.CharField(write_only=True,
                                     validators=[validate_password])

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(
            user_type='client',
            role=None,
            is_staff=False,
            is_superuser=False,
            **validated_data,
        )
        user.set_password(password)
        user.save()
        return user


class UserRoleAssignSerializer(serializers.Serializer):
    """Эндпоинт назначения типа и роли пользователя администратором.

    Принимает ``role`` или ``role_id`` (алиас для фронтенда) —
    оба поля указывают на запись в справочнике :class:`UserRole`.
    """
    user_type = serializers.ChoiceField(
        choices=User.USER_TYPE_CHOICES, required=False,
    )
    role = serializers.PrimaryKeyRelatedField(
        queryset=models.UserRole.objects.all(),
        required=False, allow_null=True,
    )
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=models.UserRole.objects.all(),
        required=False, allow_null=True, write_only=True,
    )
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        # Единый ключ ``role`` вне зависимости от того, что прислал клиент.
        if 'role_id' in attrs:
            attrs['role'] = attrs.pop('role_id')
        return attrs


class EmployeeProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = models.EmployeeProfile
        fields = ['id', 'user', 'username', 'first_name', 'last_name',
                  'middle_name', 'position', 'department', 'hire_date',
                  'internal_phone', 'notes']


class ClientProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = models.ClientProfile
        fields = ['id', 'user', 'username', 'first_name', 'last_name',
                  'middle_name', 'birth_date', 'passport_series',
                  'passport_number', 'passport_issued_by',
                  'passport_issued_date', 'passport_code',
                  'registration_address', 'actual_address',
                  'preferred_contact_method', 'notes']


# ---------- Объекты недвижимости ------------------------------------------

class PropertyFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PropertyFeature
        fields = ['id', 'name', 'category']


class PropertyFeatureValueSerializer(serializers.ModelSerializer):
    feature_name = serializers.CharField(source='feature.name', read_only=True)

    class Meta:
        model = models.PropertyFeatureValue
        fields = ['feature', 'feature_name', 'value']


class PropertyPhotoSerializer(serializers.ModelSerializer):
    """
    Фото объекта.

    Поле ``image_url`` всегда содержит итоговую ссылку, по которой можно
    отобразить фото: либо ссылка на загруженный файл, либо внешний URL.
    """
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = models.PropertyPhoto
        fields = ['id', 'property', 'image', 'url', 'image_url',
                  'caption', 'is_cover', 'is_hidden', 'order',
                  'uploaded_at']
        read_only_fields = ['uploaded_at', 'image_url']

    def get_image_url(self, obj) -> str | None:
        if obj.image:
            request = self.context.get('request')
            url = obj.image.url
            return request.build_absolute_uri(url) if request else url
        return obj.url or None


class PropertyDocumentSerializer(serializers.ModelSerializer):
    verified_by_username = serializers.CharField(source='verified_by.username',
                                                 read_only=True)

    class Meta:
        model = models.PropertyDocument
        fields = ['id', 'property', 'document_name', 'file_url',
                  'is_verified', 'verified_by', 'verified_by_username',
                  'verified_at', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class AddressNestedWriteSerializer(serializers.Serializer):
    """
    Адрес в формате «единой строки» из DaData для записи.

    Фронтенд может передавать полный набор полей, а бэкенд создаст
    (или найдёт) иерархию City → Street → House → Address.
    """
    value = serializers.CharField(max_length=500)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    street = serializers.CharField(max_length=150, required=False, allow_blank=True)
    street_type = serializers.CharField(max_length=20, required=False, allow_blank=True)
    house = serializers.CharField(max_length=20, required=False, allow_blank=True)
    block = serializers.CharField(max_length=10, required=False, allow_blank=True)
    flat = serializers.CharField(max_length=20, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    geo_lat = serializers.FloatField(required=False, allow_null=True)
    geo_lon = serializers.FloatField(required=False, allow_null=True)
    city_external_id = serializers.CharField(required=False, allow_blank=True,
                                             allow_null=True)
    street_external_id = serializers.CharField(required=False, allow_blank=True,
                                               allow_null=True)
    house_external_id = serializers.CharField(required=False, allow_blank=True,
                                              allow_null=True)


class PropertySerializer(serializers.ModelSerializer):
    """
    Сериализатор объекта.

    Для удобства фронтенда поддерживается два варианта указания адреса:
      1) ``address`` — id уже существующего ``Address``;
      2) ``address_data`` — объект с полями DaData, из которого сервер
         построит иерархию City → Street → House → Address.
    """
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    full_address = serializers.SerializerMethodField()
    # Фото возвращаем через метод, чтобы для клиентов (и неавторизованных
    # пользователей) скрывать флаг ``is_hidden`` — это и есть «ручное
    # управление альбомом» из бизнес-требований: сотрудник может спрятать
    # фото от клиента, но не удалять.
    photos = serializers.SerializerMethodField()
    feature_values = PropertyFeatureValueSerializer(many=True, read_only=True)
    feature_ids = serializers.PrimaryKeyRelatedField(
        queryset=models.PropertyFeature.objects.all(),
        many=True, required=False, write_only=True,
    )
    address_data = AddressNestedWriteSerializer(required=False, write_only=True)
    address = serializers.PrimaryKeyRelatedField(
        queryset=models.Address.objects.all(), required=False,
    )

    class Meta:
        model = models.Property
        fields = [
            'id', 'title', 'operation_type', 'operation_type_name',
            'status', 'status_name',
            'address', 'address_data', 'full_address',
            'coordinates_lat', 'coordinates_lon',
            'price', 'price_per_sqm',
            'area_total', 'area_living', 'area_kitchen',
            'rooms_count', 'floor_number', 'total_floors',
            'description', 'photos', 'feature_values', 'feature_ids',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_full_address(self, obj) -> str:
        return str(obj.address)

    def get_photos(self, obj):
        """
        Клиенту и неавторизованному пользователю возвращаем только
        видимые фото (``is_hidden=False``). Сотрудник/администратор
        видит весь альбом, чтобы управлять обложкой и скрытием.
        """
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_staff_like = bool(
            user and user.is_authenticated
            and (getattr(user, 'is_employee', False)
                 or getattr(user, 'is_superuser', False))
        )
        qs = obj.photos.all()
        if not is_staff_like:
            qs = qs.filter(is_hidden=False)
        return PropertyPhotoSerializer(
            qs, many=True, context=self.context,
        ).data

    # --- создание/обновление с построением адресной иерархии ----------

    def _resolve_address(self, address_data: dict) -> models.Address:
        """Найти или создать Address → House → Street → City по данным DaData."""
        city_name = (address_data.get('city') or '').strip() or 'Не указан'
        region = (address_data.get('region') or '').strip() or None
        city_ext = address_data.get('city_external_id') or None

        city, _ = models.City.objects.get_or_create(
            name=city_name,
            defaults={'region': region, 'external_id': city_ext},
        )
        if region and not city.region:
            city.region = region
        if city_ext and not city.external_id:
            city.external_id = city_ext
        city.save()

        street_name = (address_data.get('street') or '').strip() or '—'
        street_type = (address_data.get('street_type') or '').strip() or None
        street_ext = address_data.get('street_external_id') or None

        street, _ = models.Street.objects.get_or_create(
            city=city, name=street_name,
            defaults={'street_type': street_type, 'external_id': street_ext},
        )
        if street_type and not street.street_type:
            street.street_type = street_type
        if street_ext and not street.external_id:
            street.external_id = street_ext
        street.save()

        house_number = (address_data.get('house') or '').strip() or '—'
        block = (address_data.get('block') or '').strip() or None
        postal = (address_data.get('postal_code') or '').strip() or None
        house_ext = address_data.get('house_external_id') or None

        house, _ = models.House.objects.get_or_create(
            street=street, house_number=house_number, building=block,
            defaults={'postal_code': postal, 'external_id': house_ext},
        )
        if postal and not house.postal_code:
            house.postal_code = postal
        if house_ext and not house.external_id:
            house.external_id = house_ext
        house.save()

        flat = (address_data.get('flat') or '').strip() or None
        address, _ = models.Address.objects.get_or_create(
            house=house, apartment_number=flat,
        )
        return address

    def _apply_features(self, instance: models.Property, feature_ids):
        if feature_ids is None:
            return
        existing = {v.feature_id: v for v in instance.feature_values.all()}
        wanted_ids = {f.id for f in feature_ids}
        for fid in wanted_ids - set(existing):
            models.PropertyFeatureValue.objects.create(
                property=instance, feature_id=fid,
            )
        for fid in set(existing) - wanted_ids:
            existing[fid].delete()

    def create(self, validated_data):
        address_data = validated_data.pop('address_data', None)
        feature_ids = validated_data.pop('feature_ids', None)
        if address_data and not validated_data.get('address'):
            validated_data['address'] = self._resolve_address(address_data)
            if address_data.get('geo_lat') is not None and not validated_data.get('coordinates_lat'):
                validated_data['coordinates_lat'] = address_data['geo_lat']
            if address_data.get('geo_lon') is not None and not validated_data.get('coordinates_lon'):
                validated_data['coordinates_lon'] = address_data['geo_lon']
        if not validated_data.get('address'):
            raise serializers.ValidationError({'address': 'Адрес обязателен.'})
        instance = super().create(validated_data)
        self._apply_features(instance, feature_ids)
        return instance

    def update(self, instance, validated_data):
        address_data = validated_data.pop('address_data', None)
        feature_ids = validated_data.pop('feature_ids', None)
        if address_data:
            validated_data['address'] = self._resolve_address(address_data)
        instance = super().update(instance, validated_data)
        self._apply_features(instance, feature_ids)
        return instance


# ---------- Заяв����и, сделки, просмотры, задачи -----------------------------

class RequestPropertyMatchSerializer(serializers.ModelSerializer):
    """Вариант объекта, предложенный агентом по заявке."""
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    property_price = serializers.FloatField(source='property.price',
                                            read_only=True)
    agent_username = serializers.CharField(source='agent.username',
                                           read_only=True)

    class Meta:
        model = models.RequestPropertyMatch
        fields = ['id', 'request', 'property', 'property_title',
                  'property_price', 'agent', 'agent_username',
                  'agent_note', 'is_offered', 'is_rejected', 'created_at']
        read_only_fields = ['created_at', 'agent']


class RequestSerializer(serializers.ModelSerializer):
    """
    Заявка клиента.

    Поле ``client`` автоматически подставляется сервером, когда заявку
    подаёт клиент — ему не нужно (и он не имеет права) выбирать его
    вручную. Поле ``agent`` — опциональное: пустая заявка попадает
    в «неразобранное», откуда сотрудник забирает её действием
    ``POST /requests/{id}/take/``.
    """
    client = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type='client'),
        required=False, allow_null=True,
    )
    agent = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type='employee'),
        required=False, allow_null=True,
    )
    property = serializers.PrimaryKeyRelatedField(
        queryset=models.Property.objects.all(),
        required=False, allow_null=True,
    )
    client_username = serializers.CharField(source='client.username',
                                            read_only=True)
    agent_username = serializers.CharField(source='agent.username',
                                           read_only=True)
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_code = serializers.CharField(source='status.code', read_only=True)
    matches = RequestPropertyMatchSerializer(many=True, read_only=True)
    can_close = serializers.SerializerMethodField()

    class Meta:
        model = models.Request
        fields = [
            'id', 'client', 'client_username',
            'agent', 'agent_username',
            'property', 'property_title',
            'operation_type', 'operation_type_name',
            'status', 'status_name', 'status_code',
            'property_type', 'min_price', 'max_price',
            'min_area', 'max_area', 'rooms_count',
            'address_preferences', 'description',
            'matches', 'can_close',
            'created_at', 'updated_at', 'closed_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'closed_at']

    def get_can_close(self, obj) -> bool:
        return bool(obj.status and obj.status.code not in {'closed', 'cancelled'})


class DealSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_code = serializers.CharField(source='status.code', read_only=True)
    agent_username = serializers.CharField(source='agent.username',
                                           read_only=True)
    client_username = serializers.CharField(source='client.username',
                                            read_only=True)
    contract_url = serializers.SerializerMethodField()

    class Meta:
        model = models.Deal
        fields = ['id', 'deal_number', 'property', 'property_title',
                  'agent', 'agent_username', 'client', 'client_username',
                  'operation_type', 'operation_type_name',
                  'status', 'status_name', 'status_code',
                  'price_final', 'commission_percent', 'commission_amount',
                  'deal_date', 'notes',
                  'request', 'contract_url', 'contract_generated_at']
        read_only_fields = ['request', 'contract_generated_at']

    def get_contract_url(self, obj) -> str | None:
        """Относительный API-URL для скачивания договора (или None)."""
        if not obj.contract_file:
            return None
        return f'/api/deals/{obj.pk}/contract/'


class PropertyStatusHistorySerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    changed_by_username = serializers.CharField(source='changed_by.username',
                                                read_only=True)

    class Meta:
        model = models.PropertyStatusHistory
        fields = ['id', 'property', 'status', 'status_name',
                  'changed_by', 'changed_by_username', 'changed_at']


class PropertyViewingSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PropertyViewing
        fields = ['id', 'property', 'client', 'agent',
                  'scheduled_date', 'notes', 'created_at']
        read_only_fields = ['created_at']


class TaskSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_code = serializers.CharField(source='status.code', read_only=True)
    assignee_username = serializers.CharField(source='assignee.username',
                                              read_only=True)
    created_by_username = serializers.CharField(source='created_by.username',
                                                read_only=True)
    client_username = serializers.CharField(source='client.username',
                                            read_only=True)
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    request_client_username = serializers.CharField(
        source='request.client.username', read_only=True, default=None,
    )
    priority_display = serializers.CharField(source='get_priority_display',
                                             read_only=True)
    task_type_display = serializers.CharField(read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = models.Task
        fields = ['id', 'title', 'description', 'priority', 'priority_display',
                  'task_type', 'task_type_display',
                  'status', 'status_name', 'status_code',
                  'assignee', 'assignee_username',
                  'created_by', 'created_by_username',
                  'client', 'client_username',
                  'property', 'property_title',
                  'request', 'request_client_username', 'deal',
                  'due_date', 'completed_at', 'result', 'is_auto_closed',
                  'is_overdue', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'is_auto_closed']

    def get_is_overdue(self, obj) -> bool:
        from django.utils import timezone
        if not obj.due_date or obj.completed_at:
            return False
        if obj.status and obj.status.code in {'done', 'cancelled'}:
            return False
        return obj.due_date < timezone.now()


class OutgoingEmailSerializer(serializers.ModelSerializer):
    """Сериализатор исходящих писем."""
    recipient_username = serializers.CharField(source='recipient.username',
                                               read_only=True)
    recipient_email = serializers.CharField(source='recipient.email',
                                            read_only=True)
    sender_username = serializers.CharField(source='sender.username',
                                            read_only=True)
    status_display = serializers.CharField(source='get_status_display',
                                           read_only=True)

    class Meta:
        model = models.OutgoingEmail
        fields = ['id', 'recipient', 'recipient_username', 'recipient_email',
                  'sender', 'sender_username', 'subject', 'body',
                  'status', 'status_display', 'task', 'request', 'property',
                  'error_message', 'sent_at', 'created_at']
        read_only_fields = ['created_at', 'sent_at']
