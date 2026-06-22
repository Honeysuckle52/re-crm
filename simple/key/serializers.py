# -*- coding: utf-8 -*-
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
    max_active_tasks = serializers.IntegerField(min_value=1, required=False)
    max_in_progress_tasks = serializers.IntegerField(min_value=1, required=False)
    max_active_requests = serializers.IntegerField(min_value=1, required=False)

    class Meta:
        model = models.UserRole
        fields = [
            'id',
            'code',
            'name',
            'description',
            'max_active_tasks',
            'max_in_progress_tasks',
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
    full_name = serializers.SerializerMethodField()
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
        fields = ['id', 'username', 'email', 'phone', 'full_name',
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

    def get_full_name(self, obj):
        profile = None
        try:
            profile = getattr(obj, 'client_profile', None)
        except Exception:
            profile = None
        if profile is None:
            try:
                profile = getattr(obj, 'employee_profile', None)
            except Exception:
                profile = None
        if profile is None:
            return obj.username
        parts = [
            (profile.last_name or '').strip(),
            (profile.first_name or '').strip(),
            (profile.middle_name or '').strip(),
        ]
        full_name = ' '.join(part for part in parts if part).strip()
        return full_name or obj.username


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


class BuildingMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BuildingMaterial
        fields = ['id', 'code', 'name']


class BathroomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BathroomType
        fields = ['id', 'code', 'name']


class RenovationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RenovationType
        fields = ['id', 'code', 'name']


class CommercialPropertyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CommercialPropertyType
        fields = ['id', 'code', 'name']


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Amenity
        fields = ['id', 'code', 'name']


class PropertyOwnerSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client_profile.user.username', read_only=True)
    client_email = serializers.CharField(source='client_profile.user.email', read_only=True)
    client_phone = serializers.CharField(source='client_profile.user.phone', read_only=True)
    client_first_name = serializers.CharField(source='client_profile.first_name', read_only=True)
    client_last_name = serializers.CharField(source='client_profile.last_name', read_only=True)
    client_middle_name = serializers.CharField(source='client_profile.middle_name', read_only=True)

    class Meta:
        model = models.PropertyOwner
        fields = [
            'property', 'client_profile', 'client_username', 'client_email',
            'client_phone', 'client_first_name', 'client_last_name',
            'client_middle_name', 'ownership_share', 'created_at',
        ]
        read_only_fields = ['created_at']


class BuildingDetailsSerializer(serializers.ModelSerializer):
    building_material_data = serializers.SerializerMethodField()

    class Meta:
        model = models.BuildingDetails
        fields = [
            'id', 'house', 'year_built', 'total_floors', 'building_material',
            'building_material_data', 'elevators_count',
        ]

    def get_building_material_data(self, obj):
        material = obj.building_material
        if material is None:
            return None
        return BuildingMaterialSerializer(material).data


class PropertyDetailsSerializer(serializers.ModelSerializer):
    bathroom_type_data = serializers.SerializerMethodField()
    renovation_type_data = serializers.SerializerMethodField()

    class Meta:
        model = models.PropertyDetails
        fields = [
            'id', 'property', 'living_area', 'kitchen_area', 'ceiling_height',
            'balcony_count', 'bathroom_count', 'bathroom_type',
            'bathroom_type_data', 'renovation_type', 'renovation_type_data',
            'bedrooms_count', 'floors_count', 'land_area',
        ]

    def get_bathroom_type_data(self, obj):
        bathroom_type = obj.bathroom_type
        if bathroom_type is None:
            return None
        return BathroomTypeSerializer(bathroom_type).data

    def get_renovation_type_data(self, obj):
        renovation_type = obj.renovation_type
        if renovation_type is None:
            return None
        return RenovationTypeSerializer(renovation_type).data


class CommercialPropertyDetailsSerializer(serializers.ModelSerializer):
    commercial_type_data = serializers.SerializerMethodField()

    class Meta:
        model = models.CommercialPropertyDetails
        fields = [
            'id', 'property', 'commercial_type', 'commercial_type_data',
            'usable_area', 'ceiling_height', 'floor_load', 'electric_power_kw',
            'has_separate_entrance', 'has_display_windows', 'is_first_line',
            'parking_spaces',
        ]

    def get_commercial_type_data(self, obj):
        commercial_type = obj.commercial_type
        if commercial_type is None:
            return None
        return CommercialPropertyTypeSerializer(commercial_type).data


class PropertyAmenitySerializer(serializers.ModelSerializer):
    amenity_data = serializers.SerializerMethodField()

    class Meta:
        model = models.PropertyAmenity
        fields = ['property', 'amenity', 'amenity_data']

    def get_amenity_data(self, obj):
        amenity = obj.amenity
        if amenity is None:
            return None
        return AmenitySerializer(amenity).data


class PropertyPhotoSerializer(serializers.ModelSerializer):
    """Фото объекта с готовой ссылкой для фронта."""
    image = serializers.FileField(write_only=True, required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()
    is_cover = serializers.BooleanField(required=False)

    class Meta:
        model = models.PropertyPhoto
        fields = [
            'id', 'property', 'image', 'url', 'image_url',
            'caption', 'is_cover', 'is_hidden', 'order', 'uploaded_at',
        ]
        read_only_fields = ['uploaded_at', 'image_url']

    def _build_absolute_url(self, value):
        if not value:
            return None
        request = self.context.get('request')
        if request and hasattr(request, 'build_absolute_uri'):
            return request.build_absolute_uri(value)
        return value

    def get_image_url(self, obj) -> str | None:
        return self._build_absolute_url(obj.url)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        image = self.initial_data.get('image')
        url = self.initial_data.get('url')
        if not image and not url and not attrs.get('url'):
            raise serializers.ValidationError({'url': 'Нужно передать url или image.'})
        return attrs

    def create(self, validated_data):
        image = validated_data.pop('image', None)
        is_cover = bool(validated_data.pop('is_cover', False))
        if image:
            from django.core.files.storage import default_storage
            file_name = getattr(image, 'name', '') or 'property-photo'
            saved_path = default_storage.save(
                f'property-photos/{timezone.now():%Y/%m}/{file_name}',
                image,
            )
            validated_data['url'] = default_storage.url(saved_path)
        if is_cover:
            validated_data['order'] = 0
        return super().create(validated_data)

    def update(self, instance, validated_data):
        image = validated_data.pop('image', None)
        is_cover = validated_data.pop('is_cover', None)
        if image:
            from django.core.files.storage import default_storage
            file_name = getattr(image, 'name', '') or 'property-photo'
            saved_path = default_storage.save(
                f'property-photos/{timezone.now():%Y/%m}/{file_name}',
                image,
            )
            validated_data['url'] = default_storage.url(saved_path)
        if is_cover is True:
            validated_data['order'] = 0
        return super().update(instance, validated_data)


class PropertyDocumentSerializer(serializers.ModelSerializer):
    verified_by_username = serializers.CharField(source='verified_by.username',
                                                 read_only=True)

    class Meta:
        model = models.PropertyDocument
        fields = ['id', 'property', 'document_name', 'file_url',
                  'is_verified', 'verified_by', 'verified_by_username',
                  'verified_at', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class PropertyPriceHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True)

    class Meta:
        model = models.PropertyPriceHistory
        fields = [
            'id',
            'property',
            'old_price',
            'new_price',
            'changed_by',
            'changed_by_username',
            'changed_at',
        ]


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


class BuildingDetailsWriteSerializer(serializers.Serializer):
    year_built = serializers.IntegerField(required=False, allow_null=True, min_value=1800, max_value=2200)
    total_floors = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    building_material = serializers.PrimaryKeyRelatedField(
        queryset=models.BuildingMaterial.objects.all(),
        required=False,
        allow_null=True,
    )
    elevators_count = serializers.IntegerField(required=False, min_value=0)


class PropertyDetailsWriteSerializer(serializers.Serializer):
    living_area = serializers.DecimalField(required=False, allow_null=True, max_digits=8, decimal_places=2)
    kitchen_area = serializers.DecimalField(required=False, allow_null=True, max_digits=8, decimal_places=2)
    ceiling_height = serializers.DecimalField(required=False, allow_null=True, max_digits=4, decimal_places=2)
    balcony_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    bathroom_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    bathroom_type = serializers.PrimaryKeyRelatedField(
        queryset=models.BathroomType.objects.all(),
        required=False,
        allow_null=True,
    )
    renovation_type = serializers.PrimaryKeyRelatedField(
        queryset=models.RenovationType.objects.all(),
        required=False,
        allow_null=True,
    )
    bedrooms_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    floors_count = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    land_area = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=2)


class CommercialPropertyDetailsWriteSerializer(serializers.Serializer):
    commercial_type = serializers.PrimaryKeyRelatedField(
        queryset=models.CommercialPropertyType.objects.all(),
        required=False,
        allow_null=True,
    )
    usable_area = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=2)
    ceiling_height = serializers.DecimalField(required=False, allow_null=True, max_digits=4, decimal_places=2)
    floor_load = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=2)
    electric_power_kw = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=2)
    has_separate_entrance = serializers.BooleanField(required=False)
    has_display_windows = serializers.BooleanField(required=False)
    is_first_line = serializers.BooleanField(required=False)
    parking_spaces = serializers.IntegerField(required=False, allow_null=True, min_value=0)


class PropertyTypeField(serializers.RelatedField):
    """Принимает id или code типа помещения, нормализуя legacy office/warehouse."""

    def get_queryset(self):
        return models.PropertyType.objects.all()

    def to_representation(self, value):
        return value.code if value else None

    def to_internal_value(self, data):
        if data in (None, ''):
            return None
        if isinstance(data, models.PropertyType):
            return data
        code = str(data).strip()
        if not code:
            return None
        if code in {'office', 'warehouse'}:
            code = models.Property.PROPERTY_TYPE_COMMERCIAL
        if code.isdigit():
            obj = self.get_queryset().filter(pk=int(code)).first()
            if obj is not None:
                return obj
        obj = self.get_queryset().filter(code=code).first()
        if obj is not None:
            return obj
        raise serializers.ValidationError('Неизвестный тип помещения.')


class PropertySerializer(serializers.ModelSerializer):
    """Сериализатор объекта недвижимости."""
    PROPERTY_TYPE_SCHEMAS = {
        models.Property.PROPERTY_TYPE_APARTMENT: {
            'forbidden_top_level': ('total_floors',),
            'property_details_fields': {
                'living_area',
                'kitchen_area',
                'ceiling_height',
                'balcony_count',
                'bathroom_count',
                'bathroom_type',
                'renovation_type',
                'bedrooms_count',
            },
            'commercial_details_fields': set(),
            'required': (),
        },
        models.Property.PROPERTY_TYPE_HOUSE: {
            'forbidden_top_level': ('floor_number',),
            'property_details_fields': {
                'living_area',
                'kitchen_area',
                'ceiling_height',
                'balcony_count',
                'bathroom_count',
                'bathroom_type',
                'renovation_type',
                'bedrooms_count',
                'floors_count',
                'land_area',
            },
            'commercial_details_fields': set(),
            'required': (),
        },
        models.Property.PROPERTY_TYPE_ROOM: {
            'forbidden_top_level': ('total_floors',),
            'property_details_fields': {
                'living_area',
                'kitchen_area',
                'ceiling_height',
                'bathroom_count',
                'bathroom_type',
                'renovation_type',
                'bedrooms_count',
            },
            'commercial_details_fields': set(),
            'required': (),
        },
        models.Property.PROPERTY_TYPE_LAND: {
            'forbidden_top_level': ('rooms_count', 'floor_number', 'total_floors'),
            'property_details_fields': {'land_area'},
            'commercial_details_fields': set(),
            'required': (),
        },
        models.Property.PROPERTY_TYPE_GARAGE: {
            'forbidden_top_level': ('rooms_count', 'floor_number', 'total_floors'),
            'property_details_fields': {'renovation_type'},
            'commercial_details_fields': set(),
            'required': (),
        },
        models.Property.PROPERTY_TYPE_COMMERCIAL: {
            'forbidden_top_level': ('rooms_count', 'floor_number', 'total_floors'),
            'property_details_fields': set(),
            'commercial_details_fields': {
                'commercial_type',
                'usable_area',
                'ceiling_height',
                'floor_load',
                'electric_power_kw',
                'has_separate_entrance',
                'has_display_windows',
                'is_first_line',
                'parking_spaces',
            },
            'required': ('area_total',),
        },
    }
    _MISSING = object()

    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_code = serializers.CharField(source='status.code', read_only=True)
    property_type_name = serializers.CharField(source='property_type_ref.name', read_only=True)
    property_type_code = serializers.CharField(source='property_type_ref.code', read_only=True)
    allowed_status_ids = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()
    house_data = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    owners = serializers.SerializerMethodField()
    building_details = serializers.SerializerMethodField()
    property_details = serializers.SerializerMethodField()
    commercial_property_details = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    price_history = serializers.SerializerMethodField()
    amenity_ids = serializers.PrimaryKeyRelatedField(
        queryset=models.Amenity.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    amenities = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    owner_profile = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()
    owner_email = serializers.SerializerMethodField()
    owner_phone = serializers.SerializerMethodField()
    building_details_data = BuildingDetailsWriteSerializer(required=False, allow_null=True, write_only=True)
    property_details_data = PropertyDetailsWriteSerializer(required=False, allow_null=True, write_only=True)
    commercial_property_details_data = CommercialPropertyDetailsWriteSerializer(required=False, allow_null=True, write_only=True)
    total_floors = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    premises_type = PropertyTypeField(source='property_type_ref', required=False, allow_null=True)
    is_published = serializers.BooleanField(required=False)
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
            'address', 'address_data', 'full_address', 'house_data',
            'house', 'building_details', 'building_details_data',
            'coordinates_lat', 'coordinates_lon',
            'cadastral_number', 'property_type_name', 'property_type_code', 'premises_type', 'is_published',
            'published_at', 'unpublished_at',
            'owner', 'owner_profile', 'owner_username', 'owner_email', 'owner_phone',
            'owners', 'property_details', 'property_details_data', 'commercial_property_details', 'commercial_property_details_data',
            'amenity_ids', 'amenities', 'documents', 'price_history',
            'price', 'price_per_sqm',
            'area_total',
            'rooms_count', 'floor_number', 'total_floors',
            'description', 'photos',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'owner', 'owner_profile']
        extra_kwargs = {
            'house': {'required': False},
        }

    def get_full_address(self, obj) -> str:
        if obj.house_id is None:
            return ''
        return str(obj.house)

    def get_house_data(self, obj):
        if not obj.house_id:
            return None
        house = obj.house
        street = getattr(house, 'street', None)
        city = getattr(street, 'city', None) if street else None
        return {
            'id': house.pk,
            'house_number': house.house_number,
            'postal_code': house.postal_code,
            'external_id': str(house.external_id) if house.external_id else None,
            'street': {
                'id': street.pk if street else None,
                'name': getattr(street, 'name', None),
                'street_type': getattr(street, 'street_type', None),
                'external_id': str(getattr(street, 'external_id', None)) if getattr(street, 'external_id', None) else None,
                'city': {
                    'id': city.pk if city else None,
                    'name': getattr(city, 'name', None),
                    'region': getattr(city, 'region', None),
                    'external_id': str(getattr(city, 'external_id', None)) if getattr(city, 'external_id', None) else None,
                } if city else None,
            } if street else None,
        }

    def _serialize_owner_relation(self, relation):
        if relation is None:
            return None
        profile = relation.client_profile
        user = profile.user if profile else None
        return {
            'property': relation.property_id,
            'client_profile': profile.pk if profile else None,
            'client_username': getattr(user, 'username', None),
            'client_email': getattr(user, 'email', None),
            'client_phone': getattr(user, 'phone', None),
            'client_first_name': getattr(profile, 'first_name', None),
            'client_last_name': getattr(profile, 'last_name', None),
            'client_middle_name': getattr(profile, 'middle_name', None),
            'ownership_share': relation.ownership_share,
            'created_at': relation.created_at,
        }

    def get_owner(self, obj):
        relation = obj.owners.select_related('client_profile__user').order_by('created_at', 'client_profile_id').first()
        return relation.client_profile.user_id if relation else None

    def get_owner_profile(self, obj):
        relation = obj.owners.select_related('client_profile__user').order_by('created_at', 'client_profile_id').first()
        if relation is None:
            return None
        return PropertyOwnerSerializer(relation).data

    def get_owner_username(self, obj):
        relation = obj.owners.select_related('client_profile__user').order_by('created_at', 'client_profile_id').first()
        return relation.client_profile.user.username if relation else None

    def get_owner_email(self, obj):
        relation = obj.owners.select_related('client_profile__user').order_by('created_at', 'client_profile_id').first()
        return relation.client_profile.user.email if relation else None

    def get_owner_phone(self, obj):
        relation = obj.owners.select_related('client_profile__user').order_by('created_at', 'client_profile_id').first()
        return relation.client_profile.user.phone if relation else None

    def get_owners(self, obj):
        qs = obj.owners.select_related('client_profile__user').order_by('created_at', 'client_profile_id')
        return [self._serialize_owner_relation(relation) for relation in qs]

    def get_building_details(self, obj):
        if not obj.house_id:
            return None
        try:
            details = obj.house.building_details
        except models.BuildingDetails.DoesNotExist:
            return None
        if details is None:
            return None
        return BuildingDetailsSerializer(details).data

    def get_property_details(self, obj):
        try:
            details = obj.details
        except models.PropertyDetails.DoesNotExist:
            return None
        if details is None:
            return None
        return PropertyDetailsSerializer(details).data

    def get_commercial_property_details(self, obj):
        try:
            details = obj.commercial_details
        except models.CommercialPropertyDetails.DoesNotExist:
            return None
        if details is None:
            return None
        return CommercialPropertyDetailsSerializer(details).data

    def get_documents(self, obj):
        qs = obj.documents.all()
        return PropertyDocumentSerializer(qs, many=True, context=self.context).data

    def get_price_history(self, obj):
        qs = obj.price_history.select_related('changed_by').all()
        return PropertyPriceHistorySerializer(qs, many=True, context=self.context).data

    def _upsert_amenities(self, property_obj, payload):
        if payload is None:
            return
        models.PropertyAmenity.objects.filter(property=property_obj).delete()
        if not payload:
            return
        models.PropertyAmenity.objects.bulk_create([
            models.PropertyAmenity(property=property_obj, amenity=amenity)
            for amenity in payload
        ])

    def _upsert_building_details(self, property_obj, payload):
        if payload is None:
            return
        defaults = dict(payload)
        defaults.setdefault('elevators_count', 0)
        models.BuildingDetails.objects.update_or_create(
            house=property_obj.house,
            defaults=defaults,
        )

    def _upsert_property_details(self, property_obj, payload):
        if payload is self._MISSING:
            return
        if payload is None:
            models.PropertyDetails.objects.filter(property=property_obj).delete()
            return
        defaults = dict(payload)
        # Defaults для жилых полей применяем только когда они не гараж/земля/коммерция.
        # Гараж присылает только renovation_type — не дополняем его ненужными значениями.
        non_residential = property_obj.premises_type in (
            models.Property.PROPERTY_TYPE_GARAGE,
            models.Property.PROPERTY_TYPE_LAND,
            models.Property.PROPERTY_TYPE_COMMERCIAL,
        )
        if not non_residential:
            defaults.setdefault('balcony_count', 0)
            defaults.setdefault('bathroom_count', 1)
        models.PropertyDetails.objects.update_or_create(
            property=property_obj,
            defaults=defaults,
        )

    def _upsert_commercial_details(self, property_obj, payload):
        if payload is self._MISSING:
            return
        if payload is None:
            models.CommercialPropertyDetails.objects.filter(property=property_obj).delete()
            return
        defaults = dict(payload)
        defaults.setdefault('has_separate_entrance', False)
        defaults.setdefault('has_display_windows', False)
        defaults.setdefault('is_first_line', False)
        models.CommercialPropertyDetails.objects.update_or_create(
            property=property_obj,
            defaults=defaults,
        )

    def get_amenities(self, obj):
        qs = obj.amenities.select_related('amenity').order_by('amenity__name')
        return [PropertyAmenitySerializer(relation).data for relation in qs]

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
        return PropertyPhotoSerializer(qs, many=True, context=self.context).data

    def _resolve_owner_profile(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, models.PropertyOwner):
            return value.client_profile
        if isinstance(value, models.ClientProfile):
            return value
        if isinstance(value, User):
            return getattr(value, 'client_profile', None)
        if hasattr(value, 'client_profile'):
            return value.client_profile
        try:
            user_id = int(value)
        except (TypeError, ValueError):
            return None
        user = User.objects.select_related('client_profile').filter(pk=user_id).first()
        return getattr(user, 'client_profile', None) if user else None

    # Поля, которые не применимы для конкретного типа недвижимости.
    # Фронт уже их обнуляет, но сервер тоже должен их игнорировать/очищать.
    def _normalize_property_type_code(self, value):
        if isinstance(value, models.PropertyType):
            value = value.code
        code = (value or '').strip() if isinstance(value, str) else value
        if code in {'office', 'warehouse'}:
            return models.Property.PROPERTY_TYPE_COMMERCIAL
        return code

    def _get_property_type_schema(self, premises_type):
        return self.PROPERTY_TYPE_SCHEMAS.get(
            self._normalize_property_type_code(premises_type),
            {},
        )

    def _sanitize_nested_payload(self, payload, allowed_fields):
        if payload is self._MISSING:
            return self._MISSING
        if payload in (None, ''):
            return None
        sanitized = {
            key: value
            for key, value in dict(payload).items()
            if key in allowed_fields
        }
        return sanitized or None

    def _sanitize_property_attrs(self, attrs, instance):
        premises_type = self._normalize_property_type_code(
            attrs.get('property_type_ref', getattr(instance, 'property_type_ref', None)),
        )
        schema = self._get_property_type_schema(premises_type)
        for field in schema.get('forbidden_top_level', ()):
            if field in attrs:
                attrs[field] = None

        attrs['property_details_data'] = self._sanitize_nested_payload(
            attrs.get('property_details_data', self._MISSING),
            schema.get('property_details_fields', set()),
        )
        attrs['commercial_property_details_data'] = self._sanitize_nested_payload(
            attrs.get('commercial_property_details_data', self._MISSING),
            schema.get('commercial_details_fields', set()),
        )
        if schema.get('commercial_details_fields') or premises_type in (
            models.Property.PROPERTY_TYPE_LAND,
            models.Property.PROPERTY_TYPE_GARAGE,
        ):
            attrs['building_details_data'] = None
        return premises_type, schema

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        premises_type, schema = self._sanitize_property_attrs(attrs, instance)

        errors = {}

        # Автоматически очищаем запрещённые поля вместо ошибки,
        # чтобы фронт не мог случайно прислать мусор, и при этом
        # форма не ломалась, если поле скрыто.
        for field in schema.get('required', ()):
            val = attrs.get(field, getattr(instance, field, None))
            if val in (None, ''):
                errors[field] = f'Для данного типа объекта поле "{field}" обязательно.'

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
        building_details_data = validated_data.pop('building_details_data', None)
        property_details_data = validated_data.pop('property_details_data', self._MISSING)
        commercial_property_details_data = validated_data.pop('commercial_property_details_data', self._MISSING)
        amenity_ids = validated_data.pop('amenity_ids', None)
        if address_data and not validated_data.get('house'):
            validated_data['house'] = self._resolve_address(address_data)
            if address_data.get('geo_lat') is not None and not validated_data.get('coordinates_lat'):
                validated_data['coordinates_lat'] = address_data['geo_lat']
            if address_data.get('geo_lon') is not None and not validated_data.get('coordinates_lon'):
                validated_data['coordinates_lon'] = address_data['geo_lon']
        if not validated_data.get('house'):
            raise serializers.ValidationError({'address': 'Адрес обязателен.'})
        property_obj = super().create(validated_data)
        self._upsert_building_details(property_obj, building_details_data)
        self._upsert_property_details(property_obj, property_details_data)
        self._upsert_commercial_details(property_obj, commercial_property_details_data)
        self._upsert_amenities(property_obj, amenity_ids)
        return property_obj

    def update(self, instance, validated_data):
        address_data = validated_data.pop('address_data', None)
        building_details_data = validated_data.pop('building_details_data', None)
        property_details_data = validated_data.pop('property_details_data', self._MISSING)
        commercial_property_details_data = validated_data.pop('commercial_property_details_data', self._MISSING)
        amenity_ids = validated_data.pop('amenity_ids', None)
        if address_data:
            validated_data['house'] = self._resolve_address(address_data)
        property_obj = super().update(instance, validated_data)
        self._upsert_building_details(property_obj, building_details_data)
        self._upsert_property_details(property_obj, property_details_data)
        self._upsert_commercial_details(property_obj, commercial_property_details_data)
        self._upsert_amenities(property_obj, amenity_ids)
        return property_obj


class RequestPropertyMatchSerializer(serializers.ModelSerializer):
    """Вариант объекта, предложенный агентом по заявке."""
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    property_price = serializers.FloatField(source='property.price',
                                            read_only=True)
    agent = serializers.PrimaryKeyRelatedField(read_only=True)
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
    property_type = PropertyTypeField(
        required=False,
        allow_null=True,
    )
    client_username = serializers.CharField(source='client.username',
                                            read_only=True)
    client_full_name = serializers.SerializerMethodField()
    client_email = serializers.CharField(source='client.email', read_only=True)
    client_phone = serializers.CharField(source='client.phone', read_only=True)
    agent_username = serializers.CharField(source='agent.username',
                                           read_only=True)
    agent_full_name = serializers.SerializerMethodField()
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    property_type_code = serializers.CharField(source='property_type.code', read_only=True)
    property_type_name = serializers.CharField(source='property_type.name', read_only=True)
    status_name = serializers.CharField(
        source='status_display_name', read_only=True,
    )
    status_code = serializers.CharField(read_only=True)
    matches = RequestPropertyMatchSerializer(many=True, read_only=True)
    can_close = serializers.SerializerMethodField()

    class Meta:
        model = models.Request
        fields = [
            'id', 'client', 'client_username', 'client_full_name', 'client_email', 'client_phone',
            'agent', 'agent_username', 'agent_full_name',
            'property', 'property_title',
            'operation_type', 'operation_type_name',
            'status', 'status_name', 'status_code',
            'property_type', 'property_type_code', 'property_type_name', 'min_price', 'max_price',
            'min_area', 'max_area', 'rooms_count',
            'address_preferences', 'description',
            'matches', 'can_close',
            'created_at', 'updated_at', 'closed_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'closed_at']

    def get_can_close(self, obj) -> bool:
        return bool(obj.status_id and not obj.is_terminal)

    @staticmethod
    def _profile_full_name(profile, fallback=''):
        if profile is None:
            return fallback
        parts = [
            getattr(profile, 'last_name', '') or '',
            getattr(profile, 'first_name', '') or '',
            getattr(profile, 'middle_name', '') or '',
        ]
        full_name = ' '.join(part for part in parts if part).strip()
        return full_name or fallback

    def get_client_full_name(self, obj) -> str:
        fallback = getattr(getattr(obj, 'client', None), 'username', '') or ''
        profile = getattr(obj, 'client_profile', None)
        return self._profile_full_name(profile, fallback=fallback)

    def get_agent_full_name(self, obj) -> str:
        fallback = getattr(getattr(obj, 'agent', None), 'username', '') or ''
        profile = getattr(obj, 'employee_profile', None)
        return self._profile_full_name(profile, fallback=fallback)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        property_type = attrs.get(
            'property_type',
            getattr(instance, 'property_type', None),
        )
        property_type_code = getattr(property_type, 'code', property_type) or ''
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
        if property_type_code == models.Property.PROPERTY_TYPE_COMMERCIAL:
            if min_area in (None, '') and max_area in (None, ''):
                errors['min_area'] = 'Для офиса или склада укажите диапазон площади.'
            if rooms_count not in (None, ''):
                errors['rooms_count'] = 'Для офиса или склада количество комнат не используется.'
        else:
            if property_type_code and rooms_count in (None, '') and min_area in (None, '') and max_area in (None, ''):
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
    agent_full_name = serializers.SerializerMethodField()
    client_full_name = serializers.SerializerMethodField()
    contract_url = serializers.SerializerMethodField()
    contract_status = serializers.CharField(read_only=True)
    contract_status_display = serializers.CharField(
        source='get_contract_status_display', read_only=True,
    )
    allowed_status_ids = serializers.SerializerMethodField()

    class Meta:
        model = models.Deal
        fields = ['id', 'deal_number', 'property', 'property_title',
                  'agent', 'agent_username', 'agent_full_name',
                  'client', 'client_username',
                  'client_full_name',
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

    @staticmethod
    def _display_client_name(user) -> str:
        if user is None:
            return '—'
        profile = getattr(user, 'client_profile', None)
        if profile is None:
            return user.username or '—'
        company = getattr(profile, 'company_details', None)
        company_name = (getattr(company, 'company_name', '') or '').strip()
        if company_name:
            return company_name
        parts = [
            (profile.last_name or '').strip(),
            (profile.first_name or '').strip(),
            (profile.middle_name or '').strip(),
        ]
        full_name = ' '.join(part for part in parts if part).strip()
        return full_name or user.username or '—'

    def get_client_full_name(self, obj) -> str:
        return self._display_client_name(obj.client)

    @staticmethod
    def _display_employee_name(user) -> str:
        if user is None:
            return '—'
        profile = getattr(user, 'employee_profile', None)
        if profile is None:
            return user.username or '—'
        parts = [
            (profile.last_name or '').strip(),
            (profile.first_name or '').strip(),
            ((getattr(profile, 'middle_name', None) or '')).strip(),
        ]
        full_name = ' '.join(part for part in parts if part).strip()
        return full_name or user.username or '—'

    def get_agent_full_name(self, obj) -> str:
        return self._display_employee_name(obj.agent)

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
    client = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type='client'),
        required=False,
        allow_null=True,
        write_only=True,
    )
    agent = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type='employee'),
        required=False,
        allow_null=True,
        write_only=True,
    )
    client_profile = serializers.PrimaryKeyRelatedField(
        queryset=models.ClientProfile.objects.select_related('user').all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    employee_profile = serializers.PrimaryKeyRelatedField(
        queryset=models.EmployeeProfile.objects.select_related('user').all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    status = serializers.PrimaryKeyRelatedField(
        queryset=models.ViewingStatus.objects.all(),
        required=False,
        allow_null=True,
    )
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_code = serializers.CharField(source='status.code', read_only=True)
    client_username = serializers.CharField(source='client_profile.user.username', read_only=True)
    client_first_name = serializers.CharField(source='client_profile.first_name', read_only=True)
    client_last_name = serializers.CharField(source='client_profile.last_name', read_only=True)
    client_middle_name = serializers.CharField(source='client_profile.middle_name', read_only=True)
    client_email = serializers.CharField(source='client_profile.user.email', read_only=True)
    client_phone = serializers.CharField(source='client_profile.user.phone', read_only=True)
    agent_username = serializers.CharField(source='employee_profile.user.username', read_only=True)
    agent_first_name = serializers.CharField(source='employee_profile.first_name', read_only=True)
    agent_last_name = serializers.CharField(source='employee_profile.last_name', read_only=True)
    agent_middle_name = serializers.CharField(source='employee_profile.middle_name', read_only=True)
    agent_email = serializers.CharField(source='employee_profile.user.email', read_only=True)
    agent_phone = serializers.CharField(source='employee_profile.user.phone', read_only=True)
    scheduled_date = serializers.DateTimeField(source='viewing_date')
    payment_id = serializers.IntegerField(source='payment.id', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    payment_amount = serializers.DecimalField(
        source='payment.amount',
        read_only=True,
        max_digits=10,
        decimal_places=2,
    )
    payment_url = serializers.SerializerMethodField()
    notes = serializers.CharField(
        source='comment',
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    class Meta:
        model = models.PropertyViewing
        fields = [
            'id', 'property',
            'client', 'client_profile',
            'agent', 'employee_profile',
            'status', 'status_name', 'status_code',
            'client_username', 'client_first_name', 'client_last_name',
            'client_middle_name', 'client_email', 'client_phone',
            'agent_username', 'agent_first_name', 'agent_last_name',
            'agent_middle_name', 'agent_email', 'agent_phone',
            'scheduled_date', 'notes',
            'payment_id', 'payment_status', 'payment_amount', 'payment_url',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_payment_url(self, obj):
        payment = getattr(obj, 'payment', None)
        if payment is None:
            return None
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and (user.is_admin_or_manager or user.is_employee or user.id == obj.client_profile.user_id):
            return payment.payment_url
        return None

    def create(self, validated_data):
        client = validated_data.pop('client', None)
        agent = validated_data.pop('agent', None)
        client_profile = validated_data.pop('client_profile', None)
        employee_profile = validated_data.pop('employee_profile', None)
        if client is not None:
            validated_data['client_profile'] = getattr(client, 'client_profile', None)
        elif client_profile is not None:
            validated_data['client_profile'] = client_profile
        if agent is not None:
            validated_data['employee_profile'] = getattr(agent, 'employee_profile', None)
        elif employee_profile is not None:
            validated_data['employee_profile'] = employee_profile
        return super().create(validated_data)

    def update(self, instance, validated_data):
        client = validated_data.pop('client', None)
        agent = validated_data.pop('agent', None)
        client_profile = validated_data.pop('client_profile', None)
        employee_profile = validated_data.pop('employee_profile', None)
        if client is not None:
            instance.client = client
        elif client_profile is not None:
            instance.client_profile = client_profile
        if agent is not None:
            instance.agent = agent
        elif employee_profile is not None:
            instance.employee_profile = employee_profile
        return super().update(instance, validated_data)


class TaskSerializer(serializers.ModelSerializer):
    client = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_type='client'),
        required=False,
        allow_null=True,
    )
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
    assignee_name = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username',
                                                read_only=True)
    created_by_name = serializers.SerializerMethodField()
    client_username = serializers.CharField(source='client.username',
                                            read_only=True)
    client_name = serializers.SerializerMethodField()
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    request_client_username = serializers.CharField(
        source='request.client.username', read_only=True, default=None,
    )
    request_client_name = serializers.SerializerMethodField()
    priority_display = serializers.CharField(source='get_priority_display',
                                             read_only=True)
    task_type_display = serializers.CharField(read_only=True)
    is_overdue = serializers.SerializerMethodField()
    workflow_steps = serializers.SerializerMethodField()
    workflow_current_step = serializers.SerializerMethodField()
    showing_payment_status = serializers.SerializerMethodField()
    showing_payment_amount = serializers.SerializerMethodField()
    showing_payment_url = serializers.SerializerMethodField()
    showing_payment_id = serializers.SerializerMethodField()
    viewing_id = serializers.SerializerMethodField()
    viewing_date = serializers.SerializerMethodField()
    client_can_view_task = serializers.SerializerMethodField()

    class Meta:
        model = models.Task
        fields = ['id', 'title', 'description', 'priority', 'priority_display',
                  'task_type', 'task_type_display',
                  'status', 'status_name', 'status_code',
                  'assignee', 'assignee_username', 'assignee_name',
                  'created_by', 'created_by_username', 'created_by_name',
                  'client', 'client_username', 'client_name',
                  'property', 'property_title',
                  'request', 'request_client_username',
                  'request_client_name', 'deal',
                  'due_date', 'completed_at', 'result',
                  'steps_log', 'is_auto_closed',
                  'workflow_steps', 'workflow_current_step',
                  'showing_payment_status', 'showing_payment_amount',
                  'showing_payment_url', 'showing_payment_id',
                  'viewing_id', 'viewing_date', 'client_can_view_task',
                  'is_overdue', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'is_auto_closed', 'steps_log']
        # status назначается бэкендом автоматически при создании (статус «new»),
        # поэтому делаем поле необязательным — фронт его не передаёт.
        extra_kwargs = {
            'status': {'required': False},
        }

    def create(self, validated_data):
        client = validated_data.pop('client', None)
        if client is not None:
            validated_data['client_profile'] = getattr(client, 'client_profile', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        client = validated_data.pop('client', None)
        if client is not None:
            instance.client = client
        return super().update(instance, validated_data)

    @staticmethod
    def _display_full_name(user):
        """ФИО пользователя из профиля. Прочерк, если имя не заполнено."""
        if user is None:
            return '—'
        profile = (getattr(user, 'client_profile', None)
                   or getattr(user, 'employee_profile', None))
        if profile is None:
            return '—'
        parts = [
            (profile.last_name or '').strip(),
            (profile.first_name or '').strip(),
            (profile.middle_name or '').strip(),
        ]
        full_name = ' '.join(part for part in parts if part).strip()
        return full_name or '—'

    def get_assignee_name(self, obj) -> str:
        return self._display_full_name(obj.assignee)

    def get_created_by_name(self, obj) -> str:
        return self._display_full_name(obj.created_by)

    def get_client_name(self, obj) -> str:
        return self._display_full_name(obj.client)

    def get_request_client_name(self, obj) -> str:
        request = getattr(obj, 'request', None)
        return self._display_full_name(getattr(request, 'client', None))

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

    def _showing_payment(self, obj):
        if obj.task_type != models.Task.TASK_TYPE_SHOWING or not obj.property_id or not obj.client_id:
            return None
        viewing = models.PropertyViewing.objects.filter(
            property_id=obj.property_id,
            client_profile__user_id=obj.client_id,
        ).order_by('-viewing_date', '-id').first()
        return getattr(viewing, 'payment', None) if viewing else None

    def get_showing_payment_status(self, obj):
        payment = self._showing_payment(obj)
        return payment.status if payment else None

    def get_showing_payment_amount(self, obj):
        payment = self._showing_payment(obj)
        return payment.amount if payment else None

    def get_showing_payment_url(self, obj):
        payment = self._showing_payment(obj)
        if payment is None:
            return None
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and (
            getattr(user, 'is_admin_or_manager', False)
            or getattr(user, 'is_employee', False)
            or user.id == obj.client_id
        ):
            return payment.payment_url
        return None

    def get_showing_payment_id(self, obj):
        payment = self._showing_payment(obj)
        return payment.id if payment else None

    def get_viewing_id(self, obj):
        if obj.task_type != models.Task.TASK_TYPE_SHOWING or not obj.property_id or not obj.client_id:
            return None
        viewing = models.PropertyViewing.objects.filter(
            property_id=obj.property_id,
            client_profile__user_id=obj.client_id,
        ).order_by('-viewing_date', '-id').first()
        return viewing.id if viewing else None

    def get_viewing_date(self, obj):
        if obj.task_type != models.Task.TASK_TYPE_SHOWING or not obj.property_id or not obj.client_id:
            return None
        viewing = models.PropertyViewing.objects.filter(
            property_id=obj.property_id,
            client_profile__user_id=obj.client_id,
        ).order_by('-viewing_date', '-id').first()
        return viewing.viewing_date if viewing else None

    def get_client_can_view_task(self, obj):
        return bool(obj.client_id)


class ViewingPaymentSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client.username', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    viewing_status_code = serializers.CharField(source='viewing.status.code', read_only=True)
    invoice_id = serializers.CharField(source='sber_order_id', read_only=True)
    transaction_id = serializers.CharField(source='sber_transaction_id', read_only=True)

    class Meta:
        model = models.ViewingPayment
        fields = [
            'id',
            'viewing',
            'client',
            'client_username',
            'property',
            'property_title',
            'amount',
            'status',
            'invoice_id',
            'transaction_id',
            'sber_order_id',
            'sber_transaction_id',
            'payment_url',
            'paid_at',
            'viewing_status_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class PaymentHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True)

    class Meta:
        model = models.PaymentHistory
        fields = [
            'id',
            'payment',
            'old_status',
            'new_status',
            'comment',
            'sber_response',
            'created_at',
            'changed_by',
            'changed_by_username',
        ]
        read_only_fields = fields


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
    entity_type_code = serializers.CharField(source='entity_type.code', read_only=True)
    entity_type_display = serializers.CharField(source='entity_type.name', read_only=True)
    action_code = serializers.CharField(source='action.code', read_only=True)
    action_label = serializers.CharField(source='action.name', read_only=True)

    class Meta:
        model = models.AuditLog
        fields = [
            'id',
            'entity_type_id',
            'entity_type',
            'entity_type_code',
            'entity_type_display',
            'entity_id',
            'action_id',
            'action',
            'action_code',
            'action_label',
            'message',
            'metadata',
            'actor_id',
            'actor',
            'actor_username',
            'created_at',
        ]
        read_only_fields = fields
