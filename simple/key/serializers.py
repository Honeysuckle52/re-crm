"""Сериализаторы DRF."""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from . import business_rules, models
from . import task_workflow

User = get_user_model()

ADDRESS_MIN_LENGTH = 10


def normalize_russian_phone(value):
    if value in (None, ''):
        return None
    raw_value = str(value).strip()
    digits = re.sub(r'\D', '', raw_value)
    if len(digits) == 11 and digits[0] in {'7', '8'}:
        return f'+7{digits[1:]}'
    if len(digits) == 10:
        return f'+7{digits}'
    raise serializers.ValidationError(
        'Телефон должен быть российским номером в формате +7XXXXXXXXXX.',
    )


def validate_person_name(value, *, field_label):
    normalized = re.sub(r'\s+', ' ', (value or '').strip())
    if len(normalized) < 2:
        raise serializers.ValidationError(f'{field_label}: минимум 2 символа.')
    if not re.search(r'[A-Za-zА-Яа-яЁё]', normalized):
        raise serializers.ValidationError(f'{field_label}: укажите буквы.')
    return normalized


def validate_optional_person_name(value, *, field_label):
    if value in (None, ''):
        return value
    return validate_person_name(value, field_label=field_label)


def validate_client_address(value, *, required=False, field_label='Адрес'):
    if value in (None, ''):
        if required:
            raise serializers.ValidationError(
                f'{field_label}: заполните адрес минимум на {ADDRESS_MIN_LENGTH} символов.',
            )
        return value
    normalized = re.sub(r'\s+', ' ', str(value).strip())
    if len(normalized) < ADDRESS_MIN_LENGTH:
        raise serializers.ValidationError(
            f'{field_label}: минимум {ADDRESS_MIN_LENGTH} символов.',
        )
    if not re.search(r'[A-Za-zА-Яа-яЁё]', normalized) or not re.search(r'\d', normalized):
        raise serializers.ValidationError(
            f'{field_label}: укажите улицу/населённый пункт и номер дома.',
        )
    return normalized


def validate_passport_issuer(value):
    if value in (None, ''):
        return value
    normalized = re.sub(r'\s+', ' ', str(value).strip())
    if len(normalized) < 5:
        raise serializers.ValidationError(
            'Кем выдан: минимум 5 символов.',
        )
    if not re.search(r'[A-Za-zА-Яа-яЁё]', normalized):
        raise serializers.ValidationError(
            'Кем выдан: укажите название органа выдачи.',
        )
    return normalized


def validate_requisite_dates(attrs):
    issued_date = attrs.get('passport_issued_date')
    today = timezone.localdate()
    errors = {}
    if issued_date and issued_date > today:
        errors['passport_issued_date'] = 'Дата выдачи паспорта не может быть в будущем.'
    if errors:
        raise serializers.ValidationError(errors)


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT-вход по электронной почте вместо логина."""
    username_field = 'email'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False
        self.fields['username'] = serializers.CharField(
            required=False,
            allow_blank=True,
            write_only=True,
        )

    def validate(self, attrs):
        identifier = (
            attrs.get('email')
            or attrs.get('username')
            or ''
        ).strip()
        password = attrs.get('password')
        if not identifier:
            raise AuthenticationFailed('Укажите электронную почту.')

        if '@' in identifier:
            email = User.objects.normalize_email(identifier)
            user = User.objects.filter(email__iexact=email).first()
        else:
            user = User.objects.filter(username=identifier).first()
        if user is None:
            raise AuthenticationFailed('Неверная почта или пароль.')

        self.user = authenticate(
            request=self.context.get('request'),
            username=user.username,
            password=password,
        )
        if self.user is None or not self.user.is_active:
            raise AuthenticationFailed('Неверная почта или пароль.')
        refresh = self.get_token(self.user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


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

    def validate_code(self, value: str) -> str:
        normalized = value.strip()
        if normalized == 'closed':
            raise serializers.ValidationError(
                'Код "closed" больше не используется. Выберите один из outcome-статусов.',
            )
        return normalized


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
        fields = [
            'id', 'code', 'name', 'description',
            'max_active_tasks', 'max_in_progress_tasks',
            'max_active_requests',
        ]


class CodeNameLookupSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ['id', 'code', 'name']


class PropertyTypeSerializer(CodeNameLookupSerializer):
    class Meta(CodeNameLookupSerializer.Meta):
        model = models.PropertyType


class TaskPrioritySerializer(CodeNameLookupSerializer):
    class Meta(CodeNameLookupSerializer.Meta):
        model = models.TaskPriority


class TaskTypeSerializer(CodeNameLookupSerializer):
    class Meta(CodeNameLookupSerializer.Meta):
        model = models.TaskType


class ClientKindSerializer(CodeNameLookupSerializer):
    class Meta(CodeNameLookupSerializer.Meta):
        model = models.ClientKind


class ContactMethodSerializer(CodeNameLookupSerializer):
    class Meta(CodeNameLookupSerializer.Meta):
        model = models.ContactMethod


class ContractStatusSerializer(CodeNameLookupSerializer):
    class Meta(CodeNameLookupSerializer.Meta):
        model = models.ContractStatus


class UserTypeSerializer(CodeNameLookupSerializer):
    class Meta(CodeNameLookupSerializer.Meta):
        model = models.UserType


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
        fields = ['id', 'street', 'house_number', 'postal_code', 'external_id']


class AddressSerializer(serializers.ModelSerializer):
    house = serializers.IntegerField(source='id', read_only=True)
    full_address = serializers.SerializerMethodField()

    class Meta:
        model = models.House
        fields = ['id', 'house', 'full_address']

    def get_full_address(self, obj) -> str:
        return str(obj)


class UserSerializer(serializers.ModelSerializer):
    """Полное представление пользователя."""
    phone = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=20,
    )
    user_type = serializers.CharField(read_only=True)
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

    def validate_phone(self, value):
        return normalize_russian_phone(value)


class RegisterSerializer(serializers.ModelSerializer):
    """Регистрация клиента с одновременным созданием профиля."""
    username = serializers.CharField(
        write_only=True, max_length=50, required=False, allow_blank=True,
    )
    phone = serializers.CharField(
        write_only=True, max_length=20, required=False, allow_blank=True,
    )
    password = serializers.CharField(
        write_only=True, required=False, validators=[validate_password],
    )
    password_confirm = serializers.CharField(write_only=True, required=False)
    password_hash = serializers.CharField(write_only=True, required=False)

    first_name = serializers.CharField(write_only=True, max_length=50)
    last_name = serializers.CharField(write_only=True, max_length=50)
    middle_name = serializers.CharField(
        write_only=True, max_length=50, required=False, allow_blank=True,
    )
    client_kind = serializers.ChoiceField(
        write_only=True,
        choices=models.ClientProfile.CLIENT_KIND_CHOICES,
        required=False,
        default=models.ClientProfile.CLIENT_KIND_INDIVIDUAL,
    )
    contract_data_required = serializers.BooleanField(
        write_only=True, required=False, default=False,
    )
    passport_series = serializers.CharField(
        write_only=True, max_length=4, required=False, allow_blank=True,
        validators=[models.passport_series_validator],
    )
    passport_number = serializers.CharField(
        write_only=True, max_length=6, required=False, allow_blank=True,
        validators=[models.passport_number_validator],
    )
    passport_issued_by = serializers.CharField(
        write_only=True, max_length=255, required=False, allow_blank=True,
    )
    passport_issued_date = serializers.DateField(
        write_only=True, required=False, allow_null=True,
    )
    passport_code = serializers.CharField(
        write_only=True, max_length=7, required=False, allow_blank=True,
        validators=[models.passport_code_validator],
    )
    company_inn = serializers.CharField(
        write_only=True, max_length=10, required=False, allow_blank=True,
        validators=[models.company_inn_validator],
    )

    _PROFILE_FIELDS = (
        'first_name', 'last_name', 'middle_name', 'client_kind',
    )
    _INDIVIDUAL_FIELDS = (
        'passport_series', 'passport_number', 'passport_issued_by',
        'passport_issued_date', 'passport_code',
    )
    _COMPANY_FIELDS = ('company_inn',)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'phone',
            'password', 'password_confirm', 'password_hash',
            'first_name', 'last_name', 'middle_name', 'client_kind',
            'contract_data_required',
            'passport_series', 'passport_number', 'passport_issued_by',
            'passport_issued_date', 'passport_code',
            'company_inn',
        ]

    def validate_email(self, value):
        return User.objects.normalize_email(value).strip()

    def validate_phone(self, value):
        return normalize_russian_phone(value)

    def validate_first_name(self, value):
        return validate_person_name(value, field_label='Имя')

    def validate_last_name(self, value):
        return validate_person_name(value, field_label='Фамилия')

    def validate_middle_name(self, value):
        return validate_optional_person_name(value, field_label='Отчество')

    def validate_passport_issued_by(self, value):
        return validate_passport_issuer(value)

    def validate(self, attrs):
        validate_requisite_dates(attrs)
        has_password = bool(attrs.get('password'))
        has_password_hash = bool(attrs.get('password_hash'))
        if not has_password and not has_password_hash:
            raise serializers.ValidationError({
                'password': 'Укажите пароль.',
            })
        if has_password and attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({
                'password_confirm': 'Пароли не совпадают.',
            })
        client_kind = attrs.get(
            'client_kind',
            models.ClientProfile.CLIENT_KIND_INDIVIDUAL,
        )
        detail_fields = (
            self._INDIVIDUAL_FIELDS
            + self._COMPANY_FIELDS
        )
        has_contract_data = any(attrs.get(field) not in (None, '') for field in detail_fields)
        if not attrs.get('contract_data_required') and not has_contract_data:
            return attrs

        errors = {}
        if client_kind == models.ClientProfile.CLIENT_KIND_COMPANY:
            if not attrs.get('company_inn'):
                errors['company_inn'] = 'ИНН компании обязателен для юридического лица.'
        else:
            required_fields = {
                'passport_series': 'Серия паспорта обязательна.',
                'passport_number': 'Номер паспорта обязателен.',
                'passport_issued_by': 'Поле "Кем выдан" обязательно.',
                'passport_issued_date': 'Дата выдачи паспорта обязательна.',
                'passport_code': 'Код подразделения обязателен.',
            }
            for field, message in required_fields.items():
                if not attrs.get(field):
                    errors[field] = message
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @staticmethod
    def _generate_username(email: str) -> str:
        local_part = email.split('@', 1)[0].strip().lower()
        base = re.sub(r'[^\w.@+-]+', '_', local_part)[:40].strip('._-')
        if not base:
            base = 'client'
        candidate = base[:50]
        suffix = 1
        while User.objects.filter(username=candidate).exists():
            suffix += 1
            ending = f'-{suffix}'
            candidate = f'{base[:50 - len(ending)]}{ending}'
        return candidate

    def create(self, validated_data):
        from django.db import transaction

        username = (validated_data.pop('username', '') or '').strip()
        validated_data.pop('contract_data_required', None)
        validated_data.pop('password_confirm', None)
        password_hash = validated_data.pop('password_hash', None)
        email = validated_data.get('email')
        if not username:
            username = self._generate_username(email)
        password = validated_data.pop('password', None)
        profile_data = {f: validated_data.pop(f, None)
                        for f in self._PROFILE_FIELDS}
        individual_data = {f: validated_data.pop(f, None)
                           for f in self._INDIVIDUAL_FIELDS}
        company_data = {f: validated_data.pop(f, None)
                        for f in self._COMPANY_FIELDS}
        client_kind = (
            profile_data.pop('client_kind', None)
            or models.ClientProfile.CLIENT_KIND_INDIVIDUAL
        )
        profile_kwargs = {
            key: value for key, value in profile_data.items()
            if value not in (None, '')
        }

        with transaction.atomic():
            user = User(
                username=username,
                user_type='client',
                role=None,
                is_staff=False,
                is_superuser=False,
                **validated_data,
            )
            if password_hash:
                user.password = password_hash
            else:
                user.set_password(password)
            user.save()
            profile = models.ClientProfile.objects.create(
                user=user,
                first_name=profile_kwargs.pop('first_name'),
                last_name=profile_kwargs.pop('last_name'),
                client_kind=client_kind,
                **profile_kwargs,
            )
            if client_kind == models.ClientProfile.CLIENT_KIND_COMPANY:
                models.ClientCompanyDetails.objects.create(
                    profile=profile,
                    **{
                        key: value for key, value in company_data.items()
                        if value not in (None, '')
                    },
                )
            else:
                models.ClientIndividualDetails.objects.create(
                    profile=profile,
                    **{
                        key: value for key, value in individual_data.items()
                        if value not in (None, '')
                    },
                )
        return user


class EmailVerificationSerializer(serializers.Serializer):
    """Подтверждение email одноразовым кодом."""
    token = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=6, min_length=6, trim_whitespace=True)

    def validate_code(self, value):
        normalized = re.sub(r'\D', '', value)
        if len(normalized) != 6:
            raise serializers.ValidationError('Введите 6 цифр из письма.')
        return normalized


class EmailVerificationResendSerializer(serializers.Serializer):
    """Повторная отправка кода подтверждения."""
    token = serializers.CharField(max_length=128)


class UserRoleAssignSerializer(serializers.Serializer):
    """Назначение типа и роли пользователя."""
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
        if 'role_id' in attrs:
            attrs['role'] = attrs.pop('role_id')
        return attrs


class EmployeeProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = models.EmployeeProfile
        fields = ['id', 'user', 'username', 'first_name', 'last_name',
                  'position', 'hire_date', 'internal_phone']


class ClientProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    client_kind = serializers.ChoiceField(
        choices=models.ClientProfile.CLIENT_KIND_CHOICES,
        required=False,
    )
    preferred_contact_method = serializers.ChoiceField(
        choices=list(models.LOOKUP_NAME_DEFAULTS['ContactMethod'].items()),
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    passport_series = serializers.CharField(
        max_length=4, required=False, allow_blank=True, allow_null=True,
        write_only=True,
        validators=[models.passport_series_validator],
    )
    passport_number = serializers.CharField(
        max_length=6, required=False, allow_blank=True, allow_null=True,
        write_only=True,
        validators=[models.passport_number_validator],
    )
    passport_issued_by = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True,
        write_only=True,
    )
    passport_issued_date = serializers.DateField(
        required=False, allow_null=True, write_only=True,
    )
    passport_code = serializers.CharField(
        max_length=7, required=False, allow_blank=True, allow_null=True,
        write_only=True,
        validators=[models.passport_code_validator],
    )
    company_inn = serializers.CharField(
        max_length=10, required=False, allow_blank=True, allow_null=True,
        write_only=True,
        validators=[models.company_inn_validator],
    )

    _INDIVIDUAL_FIELDS = (
        'passport_series', 'passport_number',
        'passport_issued_by', 'passport_issued_date', 'passport_code',
    )
    _COMPANY_FIELDS = ('company_inn',)

    class Meta:
        model = models.ClientProfile
        fields = ['id', 'user', 'username', 'first_name', 'last_name',
                  'middle_name', 'client_kind', 'passport_series',
                  'passport_number', 'passport_issued_by',
                  'passport_issued_date', 'passport_code',
                  'company_inn',
                  'preferred_contact_method']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        individual = getattr(instance, 'individual_details', None)
        company = getattr(instance, 'company_details', None)
        for field in self._INDIVIDUAL_FIELDS:
            data[field] = getattr(individual, field, None) if individual else None
        for field in self._COMPANY_FIELDS:
            data[field] = getattr(company, field, None) if company else None
        return data

    def validate_first_name(self, value):
        return validate_person_name(value, field_label='Имя')

    def validate_last_name(self, value):
        return validate_person_name(value, field_label='Фамилия')

    def validate_middle_name(self, value):
        return validate_optional_person_name(value, field_label='Отчество')

    def validate_passport_issued_by(self, value):
        return validate_passport_issuer(value)

    @staticmethod
    def _has_value(value):
        return value not in (None, '')

    def _merged_contract_data(self, attrs):
        instance = self.instance
        data = {
            'first_name': attrs.get(
                'first_name',
                getattr(instance, 'first_name', None),
            ),
            'last_name': attrs.get(
                'last_name',
                getattr(instance, 'last_name', None),
            ),
            'middle_name': attrs.get(
                'middle_name',
                getattr(instance, 'middle_name', None),
            ),
            'client_kind': attrs.get(
                'client_kind',
                getattr(
                    instance,
                    'client_kind',
                    models.ClientProfile.CLIENT_KIND_INDIVIDUAL,
                ),
            ),
        }
        individual = getattr(instance, 'individual_details', None)
        for field in self._INDIVIDUAL_FIELDS:
            data[field] = attrs.get(
                field,
                getattr(individual, field, None) if individual else None,
            )
        company = getattr(instance, 'company_details', None)
        for field in self._COMPANY_FIELDS:
            data[field] = attrs.get(
                field,
                getattr(company, field, None) if company else None,
            )
        return data

    @staticmethod
    def _merge_serializer_errors(errors, exc):
        detail = exc.detail
        if isinstance(detail, dict):
            errors.update(detail)
        else:
            errors['detail'] = detail

    def validate(self, attrs):
        merged = self._merged_contract_data(attrs)
        errors = {}

        for field, label in (
            ('first_name', 'Имя'),
            ('last_name', 'Фамилия'),
        ):
            if not self._has_value(merged.get(field)):
                errors[field] = f'{label}: поле обязательно.'
                continue
            try:
                validate_person_name(merged[field], field_label=label)
            except serializers.ValidationError as exc:
                errors[field] = exc.detail

        try:
            validate_optional_person_name(
                merged.get('middle_name'),
                field_label='Отчество',
            )
        except serializers.ValidationError as exc:
            errors['middle_name'] = exc.detail

        if merged.get('client_kind') == models.ClientProfile.CLIENT_KIND_COMPANY:
            company_inn = merged.get('company_inn')
            if not self._has_value(company_inn):
                errors['company_inn'] = 'ИНН компании обязателен для юридического лица.'
            elif not re.fullmatch(r'\d{10}', str(company_inn)):
                errors['company_inn'] = 'ИНН юридического лица должен состоять из 10 цифр.'
        else:
            required_fields = {
                'passport_series': 'Серия паспорта обязательна.',
                'passport_number': 'Номер паспорта обязателен.',
                'passport_issued_by': 'Поле "Кем выдан" обязательно.',
                'passport_issued_date': 'Дата выдачи паспорта обязательна.',
                'passport_code': 'Код подразделения обязателен.',
            }
            for field, message in required_fields.items():
                if not self._has_value(merged.get(field)):
                    errors[field] = message

            patterns = {
                'passport_series': (r'\d{4}', 'Серия паспорта должна состоять из 4 цифр.'),
                'passport_number': (r'\d{6}', 'Номер паспорта должен состоять из 6 цифр.'),
                'passport_code': (r'\d{3}-\d{3}', 'Код подразделения должен быть в формате 000-000.'),
            }
            for field, (pattern, message) in patterns.items():
                value = merged.get(field)
                if self._has_value(value) and not re.fullmatch(pattern, str(value)):
                    errors[field] = message
            if self._has_value(merged.get('passport_issued_by')):
                try:
                    validate_passport_issuer(merged['passport_issued_by'])
                except serializers.ValidationError as exc:
                    errors['passport_issued_by'] = exc.detail

            try:
                validate_requisite_dates(merged)
            except serializers.ValidationError as exc:
                self._merge_serializer_errors(errors, exc)

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _pop_detail_data(self, validated_data):
        individual = {
            field: validated_data.pop(field)
            for field in self._INDIVIDUAL_FIELDS
            if field in validated_data
        }
        company = {
            field: validated_data.pop(field)
            for field in self._COMPANY_FIELDS
            if field in validated_data
        }
        return individual, company

    @staticmethod
    def _normalize_detail_value(value):
        return None if value == '' else value

    def _save_details(self, profile, individual_data, company_data):
        if profile.client_kind == models.ClientProfile.CLIENT_KIND_COMPANY:
            models.ClientIndividualDetails.objects.filter(profile=profile).delete()
            details, _ = models.ClientCompanyDetails.objects.get_or_create(
                profile=profile,
            )
            for key, value in company_data.items():
                setattr(details, key, self._normalize_detail_value(value))
            details.save()
            return

        models.ClientCompanyDetails.objects.filter(profile=profile).delete()
        details, _ = models.ClientIndividualDetails.objects.get_or_create(
            profile=profile,
        )
        for key, value in individual_data.items():
            setattr(details, key, self._normalize_detail_value(value))
        details.save()

    def create(self, validated_data):
        individual_data, company_data = self._pop_detail_data(validated_data)
        profile = super().create(validated_data)
        self._save_details(profile, individual_data, company_data)
        return profile

    def update(self, instance, validated_data):
        individual_data, company_data = self._pop_detail_data(validated_data)
        profile = super().update(instance, validated_data)
        self._save_details(profile, individual_data, company_data)
        return profile


class PropertyPhotoSerializer(serializers.ModelSerializer):
    """Фото объекта с готовой ссылкой для фронта."""
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
    """Данные адреса из DaData для записи."""
    value = serializers.CharField(max_length=500)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    street = serializers.CharField(max_length=150, required=False, allow_blank=True)
    street_type = serializers.CharField(max_length=20, required=False, allow_blank=True)
    house = serializers.CharField(max_length=20, required=False, allow_blank=True)
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
    """Сериализатор объекта недвижимости."""
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_code = serializers.CharField(source='status.code', read_only=True)
    allowed_status_ids = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_phone = serializers.CharField(source='owner.phone', read_only=True)
    premises_type = serializers.ChoiceField(
        choices=models.Property.PREMISES_TYPE_CHOICES,
        required=False,
    )
    price_per_sqm = serializers.FloatField(read_only=True)
    address_data = AddressNestedWriteSerializer(required=False, write_only=True)
    address = serializers.PrimaryKeyRelatedField(
        queryset=models.House.objects.all(),
        source='house',
        required=False,
    )

    class Meta:
        model = models.Property
        fields = [
            'id', 'title', 'operation_type', 'operation_type_name',
            'status', 'status_name', 'status_code', 'allowed_status_ids',
            'address', 'address_data', 'full_address',
            'coordinates_lat', 'coordinates_lon',
            'premises_type', 'owner', 'owner_username', 'owner_email', 'owner_phone',
            'price', 'price_per_sqm',
            'area_total',
            'rooms_count', 'floor_number', 'total_floors',
            'description', 'photos',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_full_address(self, obj) -> str:
        if obj.house_id is None:
            return ''
        return str(obj.house)

    def get_allowed_status_ids(self, obj) -> list[int]:
        statuses_by_code = self.context.setdefault(
            '_property_status_ids_by_code',
            {
                status.code: status.pk
                for status in models.PropertyStatus.objects.all()
            },
        )
        return [
            status_id
            for code in business_rules.property_allowed_transition_codes(obj)
            if (status_id := statuses_by_code.get(code)) is not None
        ]

    def get_photos(self, obj):
        """Клиенту отдаём только видимые фото."""
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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        premises_type = attrs.get(
            'premises_type',
            getattr(instance, 'premises_type', None),
        )
        rooms_count = attrs.get(
            'rooms_count',
            getattr(instance, 'rooms_count', None),
        )
        floor_number = attrs.get(
            'floor_number',
            getattr(instance, 'floor_number', None),
        )
        total_floors = attrs.get(
            'total_floors',
            getattr(instance, 'total_floors', None),
        )
        area_total = attrs.get(
            'area_total',
            getattr(instance, 'area_total', None),
        )

        errors = {}
        if premises_type == models.Property.PREMISES_APARTMENT:
            pass
        elif premises_type == models.Property.PREMISES_HOUSE:
            if floor_number not in (None, ''):
                errors['floor_number'] = 'Для дома отдельный этаж не указывается.'
            if total_floors in (None, ''):
                errors['total_floors'] = 'Для дома укажите количество этажей.'
        elif premises_type == models.Property.PREMISES_WAREHOUSE:
            if area_total in (None, ''):
                errors['area_total'] = 'Для склада укажите площадь.'
            if rooms_count not in (None, ''):
                errors['rooms_count'] = 'Для склада количество комнат не используется.'
            if floor_number not in (None, ''):
                errors['floor_number'] = 'Для склада этаж не указывается.'
            if total_floors not in (None, ''):
                errors['total_floors'] = 'Для склада количество этажей не указывается.'
        elif premises_type == models.Property.PREMISES_OFFICE:
            if area_total in (None, ''):
                errors['area_total'] = 'Для офиса укажите площадь.'
            if rooms_count not in (None, ''):
                errors['rooms_count'] = 'Для офиса количество комнат не используется.'

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _resolve_address(self, address_data: dict) -> models.House:
        """Найти или создать House → Street → City по данным DaData."""
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
        postal = (address_data.get('postal_code') or '').strip() or None
        house_ext = address_data.get('house_external_id') or None

        house, _ = models.House.objects.get_or_create(
            street=street, house_number=house_number,
            defaults={'postal_code': postal, 'external_id': house_ext},
        )
        if postal and not house.postal_code:
            house.postal_code = postal
        if house_ext and not house.external_id:
            house.external_id = house_ext
        house.save()
        return house

    def create(self, validated_data):
        address_data = validated_data.pop('address_data', None)
        if address_data and not validated_data.get('house'):
            validated_data['house'] = self._resolve_address(address_data)
            if address_data.get('geo_lat') is not None and not validated_data.get('coordinates_lat'):
                validated_data['coordinates_lat'] = address_data['geo_lat']
            if address_data.get('geo_lon') is not None and not validated_data.get('coordinates_lon'):
                validated_data['coordinates_lon'] = address_data['geo_lon']
        if not validated_data.get('house'):
            raise serializers.ValidationError({'address': 'Адрес обязателен.'})
        return super().create(validated_data)

    def update(self, instance, validated_data):
        address_data = validated_data.pop('address_data', None)
        if address_data:
            validated_data['house'] = self._resolve_address(address_data)
        return super().update(instance, validated_data)


class RequestPropertyMatchSerializer(serializers.ModelSerializer):
    """Вариант объекта, предложенный агентом по заявке."""
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    property_price = serializers.FloatField(source='property.price',
                                            read_only=True)
    agent_username = serializers.CharField(source='agent.username',
                                           read_only=True)
    confirmed_by_username = serializers.CharField(
        source='confirmed_by.username', read_only=True,
    )
    state = serializers.CharField(source='state_code', read_only=True)

    class Meta:
        model = models.RequestPropertyMatch
        fields = ['id', 'request', 'property', 'property_title',
                  'property_price', 'agent', 'agent_username',
                  'agent_note',
                  'is_offered', 'is_rejected', 'is_confirmed',
                  'confirmed_at', 'confirmed_by', 'confirmed_by_username',
                  'state', 'created_at']
        read_only_fields = ['created_at', 'agent', 'confirmed_at',
                            'confirmed_by', 'confirmed_by_username',
                            'state']


class RequestSerializer(serializers.ModelSerializer):
    """Заявка клиента."""
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
    client_email = serializers.CharField(source='client.email', read_only=True)
    client_phone = serializers.CharField(source='client.phone', read_only=True)
    agent_username = serializers.CharField(source='agent.username',
                                           read_only=True)
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(
        source='status_display_name', read_only=True,
    )
    status_code = serializers.CharField(read_only=True)
    matches = RequestPropertyMatchSerializer(many=True, read_only=True)
    can_close = serializers.SerializerMethodField()

    class Meta:
        model = models.Request
        fields = [
            'id', 'client', 'client_username', 'client_email', 'client_phone',
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
        return bool(obj.status_id and not obj.is_terminal)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        property_type = (attrs.get(
            'property_type',
            getattr(instance, 'property_type', None),
        ) or '').strip()
        rooms_count = attrs.get(
            'rooms_count',
            getattr(instance, 'rooms_count', None),
        )
        min_area = attrs.get(
            'min_area',
            getattr(instance, 'min_area', None),
        )
        max_area = attrs.get(
            'max_area',
            getattr(instance, 'max_area', None),
        )

        errors = {}
        if property_type in {
            models.Property.PREMISES_OFFICE,
            models.Property.PREMISES_WAREHOUSE,
        }:
            if min_area in (None, '') and max_area in (None, ''):
                errors['min_area'] = 'Для офиса или склада укажите диапазон площади.'
            if rooms_count not in (None, ''):
                errors['rooms_count'] = 'Для офиса или склада количество комнат не используется.'
        else:
            if property_type and rooms_count in (None, '') and min_area in (None, '') and max_area in (None, ''):
                errors['property_type'] = 'Укажите параметры, соответствующие выбранному типу помещения.'

        if min_area not in (None, '') and max_area not in (None, ''):
            try:
                if float(min_area) > float(max_area):
                    errors['min_area'] = 'Минимальная площадь не может быть больше максимальной.'
            except (TypeError, ValueError):
                pass

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class RequestCloseSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=[
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
        ('rejected', 'rejected'),
        ('lost', 'lost'),
    ])


class BulkIdsSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        if not unique_ids:
            raise serializers.ValidationError('Выберите хотя бы одну запись.')
        return unique_ids


class RequestBulkCloseSerializer(BulkIdsSerializer):
    outcome = serializers.ChoiceField(choices=[
        ('completed', 'completed'),
        ('cancelled', 'cancelled'),
        ('rejected', 'rejected'),
        ('lost', 'lost'),
    ])


class TaskBulkActionSerializer(BulkIdsSerializer):
    action = serializers.ChoiceField(choices=[
        ('pause', 'pause'),
        ('complete', 'complete'),
        ('delete', 'delete'),
    ])
    result = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


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
    contract_status = serializers.CharField(read_only=True)
    contract_status_display = serializers.CharField(
        source='get_contract_status_display', read_only=True,
    )
    allowed_status_ids = serializers.SerializerMethodField()

    class Meta:
        model = models.Deal
        fields = ['id', 'deal_number', 'property', 'property_title',
                  'agent', 'agent_username', 'client', 'client_username',
                  'operation_type', 'operation_type_name',
                  'status', 'status_name', 'status_code',
                  'price_final', 'commission_percent', 'commission_amount',
                  'deal_date', 'notes',
                  'request', 'contract_url',
                  'allowed_status_ids',
                  'contract_status', 'contract_status_display',
                  'contract_error_message', 'contract_requested_at',
                  'contract_generated_at']
        read_only_fields = [
            'request', 'contract_url',
            'allowed_status_ids',
            'contract_status', 'contract_status_display',
            'contract_error_message', 'contract_requested_at',
            'contract_generated_at',
        ]

    def get_contract_url(self, obj) -> str | None:
        """URL скачивания договора."""
        if not obj.contract_file or obj.contract_status != 'ready':
            return None
        return f'/api/deals/{obj.pk}/contract/'

    def get_allowed_status_ids(self, obj) -> list[int]:
        statuses_by_code = self.context.setdefault(
            '_deal_status_ids_by_code',
            {
                status.code: status.pk
                for status in models.DealStatus.objects.all()
            },
        )
        return [
            status_id
            for code in business_rules.deal_allowed_transition_codes(obj)
            if (status_id := statuses_by_code.get(code)) is not None
        ]


class PropertyStatusHistorySerializer(serializers.ModelSerializer):
    status = serializers.IntegerField(source='new_status_id', read_only=True)
    old_status = serializers.IntegerField(source='old_status_id', read_only=True)
    new_status = serializers.IntegerField(source='new_status_id', read_only=True)
    status_name = serializers.CharField(source='new_status.name', read_only=True)
    old_status_name = serializers.CharField(source='old_status.name', read_only=True)
    new_status_name = serializers.CharField(source='new_status.name', read_only=True)
    changed_by_username = serializers.CharField(source='changed_by.username',
                                                read_only=True)

    class Meta:
        model = models.PropertyStatusHistory
        fields = ['id', 'property', 'status', 'status_name',
                  'old_status', 'old_status_name',
                  'new_status', 'new_status_name',
                  'changed_by', 'changed_by_username', 'changed_at']


class PropertyViewingSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PropertyViewing
        fields = ['id', 'property', 'client', 'agent',
                  'scheduled_date', 'notes', 'created_at']
        read_only_fields = ['created_at']


class TaskSerializer(serializers.ModelSerializer):
    priority = serializers.ChoiceField(
        choices=models.Task.PRIORITY_CHOICES,
        required=False,
    )
    task_type = serializers.ChoiceField(
        choices=models.Task.TASK_TYPE_CHOICES,
        required=False,
    )
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
    workflow_steps = serializers.SerializerMethodField()
    workflow_current_step = serializers.SerializerMethodField()

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
                  'due_date', 'completed_at', 'result',
                  'steps_log', 'is_auto_closed',
                  'workflow_steps', 'workflow_current_step',
                  'is_overdue', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'is_auto_closed', 'steps_log']
        # status назначается бэкендом автоматически при создании (статус «new»),
        # поэтому делаем поле необязательным — фронт его не передаёт.
        extra_kwargs = {
            'status': {'required': False},
        }

    def get_is_overdue(self, obj) -> bool:
        from django.utils import timezone
        if not obj.due_date or obj.completed_at:
            return False
        if obj.status and obj.status.code in {'done', 'cancelled'}:
            return False
        return obj.due_date < timezone.now()

    def get_workflow_steps(self, obj) -> list[dict]:
        return task_workflow.workflow_payload(obj)

    def get_workflow_current_step(self, obj) -> str:
        return task_workflow.current_step_id(obj)


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
                  'html_body',
                  'trigger_code', 'context',
                  'status', 'status_display', 'task', 'request', 'property',
                  'error_message', 'processing_started_at',
                  'sent_at', 'created_at']
        read_only_fields = ['created_at', 'processing_started_at', 'sent_at']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)
    entity_type_display = serializers.CharField(source='get_entity_type_display', read_only=True)

    class Meta:
        model = models.AuditLog
        fields = [
            'id',
            'entity_type',
            'entity_type_display',
            'entity_id',
            'action_code',
            'action_label',
            'message',
            'metadata',
            'actor',
            'actor_username',
            'property',
            'request',
            'task',
            'deal',
            'created_at',
        ]
        read_only_fields = fields
