"""DRF-сериализаторы приложения `key`."""
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


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserRole
        fields = ['id', 'code', 'name', 'description']


# ---------- Адреса ---------------------------------------------------------

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.City
        fields = ['id', 'name', 'region', 'fias_id']


class StreetSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = models.Street
        fields = ['id', 'city', 'city_name', 'name', 'street_type', 'fias_id']


class HouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.House
        fields = ['id', 'street', 'house_number', 'building',
                  'structure', 'postal_code', 'fias_id']


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
    role_name = serializers.CharField(source='role.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'user_type',
                  'role', 'role_name', 'is_active', 'is_email_verified',
                  'is_phone_verified', 'created_at']
        read_only_fields = ['id', 'created_at']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password',
                  'user_type', 'role']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


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
    class Meta:
        model = models.PropertyPhoto
        fields = ['id', 'property', 'url', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class PropertyDocumentSerializer(serializers.ModelSerializer):
    verified_by_username = serializers.CharField(source='verified_by.username',
                                                 read_only=True)

    class Meta:
        model = models.PropertyDocument
        fields = ['id', 'property', 'document_name', 'file_url',
                  'is_verified', 'verified_by', 'verified_by_username',
                  'verified_at', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class PropertySerializer(serializers.ModelSerializer):
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    full_address = serializers.SerializerMethodField()
    photos = PropertyPhotoSerializer(many=True, read_only=True)
    feature_values = PropertyFeatureValueSerializer(many=True, read_only=True)

    class Meta:
        model = models.Property
        fields = [
            'id', 'title', 'operation_type', 'operation_type_name',
            'status', 'status_name', 'address', 'full_address',
            'coordinates_lat', 'coordinates_lon',
            'price', 'price_per_sqm',
            'area_total', 'area_living', 'area_kitchen',
            'rooms_count', 'floor_number', 'total_floors',
            'description', 'photos', 'feature_values',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_full_address(self, obj) -> str:
        return str(obj.address)


# ---------- Заявки, сделки, просмотры -------------------------------------

class RequestSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client.username',
                                            read_only=True)
    agent_username = serializers.CharField(source='agent.username',
                                           read_only=True)
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)

    class Meta:
        model = models.Request
        fields = [
            'id', 'client', 'client_username', 'agent', 'agent_username',
            'operation_type', 'operation_type_name',
            'status', 'status_name',
            'property_type', 'min_price', 'max_price',
            'min_area', 'max_area', 'rooms_count',
            'address_preferences', 'description',
            'created_at', 'updated_at', 'closed_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class DealSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title',
                                           read_only=True)
    operation_type_name = serializers.CharField(source='operation_type.name',
                                                read_only=True)

    class Meta:
        model = models.Deal
        fields = ['id', 'deal_number', 'property', 'property_title',
                  'agent', 'client', 'operation_type', 'operation_type_name',
                  'price_final', 'commission_percent', 'commission_amount',
                  'deal_date']


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
