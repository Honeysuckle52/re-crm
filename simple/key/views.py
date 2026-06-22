# -*- coding: utf-8 -*-
"""API приложения ``key``."""
import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Sum, Q, F
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets, filters, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer as BaseTokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from django.http import FileResponse, Http404

from . import audit as audit_service
from . import email_verification
from . import business_rules, data_exchange, deals_service, models, reports, serializers
from .business_rules import WorkloadLimitExceeded
from .dadata import DadataClient
from .twogis import TwoGisClient, apply_property_enrichment
from .mailing import (
    resend as resend_email,
    enqueue_task_assigned,
)
from .viewing_payments import (
    SberAcquiringError,
    ViewingPaymentAccessDenied,
    ViewingPaymentValidationError,
    create_viewing_payment,
    mark_payment_failed,
    refund_payment,
    sync_payment_with_sber,
)
from .permissions import (
    IsAdminOrManager,
    IsClientOrAdminOrManager,
    IsEmployee,
    IsEmployeeOrReadOnly,
    IsAdminOrManagerOrReadOnly,
    IsOwnClientProfileOrEmployee,
)
from . import request_lifecycle

User = get_user_model()
log = logging.getLogger(__name__)


class TokenRefreshSerializer(BaseTokenRefreshSerializer):
    """Refresh serializer that returns 401 for tokens referencing deleted users."""

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist as exc:
            raise InvalidToken('User not found') from exc


class TokenRefreshView(BaseTokenRefreshView):
    serializer_class = TokenRefreshSerializer


def _employee_visible_requests_q(user, *, prefix: str = '') -> Q:
    agent_lookup = f'{prefix}agent'
    return (
        Q(**{agent_lookup: user})
        | (
            Q(**{f'{agent_lookup}__isnull': True})
            & Q(**{
                f'{prefix}status__code__in': models.Request.ACTIVE_STATUS_CODES,
            })
        )
    )


def _parse_bool_param(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'y'}:
        return True
    if normalized in {'0', 'false', 'no', 'n'}:
        return False
    return None


def _validation_error_payload(exc: ValidationError):
    detail = exc.detail
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, (list, tuple)):
        return {'detail': detail[0] if detail else 'Ошибка валидации.'}
    return {'detail': detail}


def _parse_date_filter_value(raw_value: str | None, *, field_name: str):
    if raw_value in (None, ''):
        return None
    parsed = parse_date(str(raw_value).strip())
    if parsed is None:
        raise ValidationError({
            field_name: [f'Неверный формат даты для параметра "{field_name}".'],
        })
    return parsed


def _apply_date_range_filter(
    qs,
    params,
    *,
    field_name: str,
    start_param: str = 'date_from',
    end_param: str = 'date_to',
    use_date_lookup: bool = False,
):
    start_date = _parse_date_filter_value(
        params.get(start_param),
        field_name=start_param,
    )
    end_date = _parse_date_filter_value(
        params.get(end_param),
        field_name=end_param,
    )
    lookup_field = f'{field_name}__date' if use_date_lookup else field_name
    if start_date:
        qs = qs.filter(**{f'{lookup_field}__gte': start_date})
    if end_date:
        qs = qs.filter(**{f'{lookup_field}__lte': end_date})
    return qs


def _task_operation_filter_q(operation_type_id) -> Q:
    return (
        Q(request__operation_type_id=operation_type_id)
        | Q(deal__operation_type_id=operation_type_id)
        | Q(property__operation_type_id=operation_type_id)
    )


def _apply_property_filters(qs, params):
    if params.get('operation_type'):
        qs = qs.filter(operation_type_id=params['operation_type'])
    if params.get('status'):
        qs = qs.filter(status_id=params['status'])
    if params.get('rooms'):
        rooms = str(params['rooms']).strip()
        if rooms.endswith('+') and rooms[:-1].isdigit():
            qs = qs.filter(rooms_count__gte=int(rooms[:-1]))
        else:
            qs = qs.filter(rooms_count=rooms)
    if params.get('floor_number'):
        qs = qs.filter(floor_number=params['floor_number'])
    if params.get('total_floors'):
        total_floors = str(params['total_floors']).strip()
        if total_floors.endswith('+') and total_floors[:-1].isdigit():
            qs = qs.filter(house__building_details__total_floors__gte=int(total_floors[:-1]))
        else:
            qs = qs.filter(house__building_details__total_floors=total_floors)
    if params.get('floor_number__gt'):
        qs = qs.filter(floor_number__gt=params['floor_number__gt'])
    if params.get('min_area'):
        qs = qs.filter(area_total__gte=params['min_area'])
    if params.get('max_area'):
        qs = qs.filter(area_total__lte=params['max_area'])
    premises_type = (params.get('premises_type') or '').strip()
    if premises_type:
        qs = qs.filter(property_type_ref__code=premises_type)
    owner = (params.get('owner') or '').strip()
    if owner and owner != 'me':
        qs = qs.filter(owners__client_profile__user_id=owner).distinct()
    if params.get('min_price'):
        qs = qs.filter(price__gte=params['min_price'])
    if params.get('max_price'):
        qs = qs.filter(price__lte=params['max_price'])
    if params.get('renovation_type'):
        qs = qs.filter(details__renovation_type_id=params['renovation_type'])
    if params.get('bathroom_type'):
        qs = qs.filter(details__bathroom_type_id=params['bathroom_type'])
    if params.get('building_material'):
        qs = qs.filter(house__building_details__building_material_id=params['building_material'])
    if params.get('commercial_type'):
        qs = qs.filter(commercial_details__commercial_type_id=params['commercial_type'])
    if _parse_bool_param(params.get('has_separate_entrance')) is True:
        qs = qs.filter(commercial_details__has_separate_entrance=True)
    if _parse_bool_param(params.get('is_first_line')) is True:
        qs = qs.filter(commercial_details__is_first_line=True)
    if _parse_bool_param(params.get('has_display_windows')) is True:
        qs = qs.filter(commercial_details__has_display_windows=True)
    if params.get('min_parking_spaces'):
        qs = qs.filter(commercial_details__parking_spaces__gte=params['min_parking_spaces'])
    if params.get('min_land_area'):
        qs = qs.filter(details__land_area__gte=params['min_land_area'])
    if params.get('max_land_area'):
        qs = qs.filter(details__land_area__lte=params['max_land_area'])
    if params.get('year_built_from'):
        qs = qs.filter(house__building_details__year_built__gte=params['year_built_from'])
    if params.get('year_built_to'):
        qs = qs.filter(house__building_details__year_built__lte=params['year_built_to'])
    if _parse_bool_param(params.get('not_last_floor')) is True:
        qs = qs.filter(
            Q(floor_number__lt=F('house__building_details__total_floors')),
        )
    amenity_ids = (params.get('amenity_ids') or '').strip()
    if amenity_ids:
        for raw_id in [part.strip() for part in amenity_ids.split(',') if part.strip()]:
            qs = qs.filter(amenities__amenity_id=raw_id)
        qs = qs.distinct()
    search = (params.get('search') or '').strip()
    if search:
        search_filter = (
            Q(title__icontains=search)
            | Q(description__icontains=search)
        )
        if search.isdigit():
            search_filter |= Q(pk=int(search))
        qs = qs.filter(search_filter)
    qs = _apply_date_range_filter(
        qs,
        params,
        field_name='created_at',
    )
    ordering = (params.get('ordering') or '').strip()
    if ordering in {
        'price', '-price',
        'created_at', '-created_at',
        'area_total', '-area_total',
    }:
        qs = qs.order_by(ordering)
    return qs


@transaction.atomic
def _pause_task_instance(task, *, actor):
    task = (
        models.Task.objects
        .select_for_update()
        .select_related('status')
        .get(pk=task.pk)
    )
    waiting = business_rules.status_by_code(
        models.TaskStatus,
        'waiting',
    )
    if not waiting:
        raise ValidationError(
            {'detail': 'Справочник статусов не заполнен.'},
        )

    old_status_code = task.status.code if task.status_id else None
    old_status = task.status
    task.status = waiting
    update_fields = ['status', 'updated_at']
    if old_status_code in models.Task.TERMINAL_STATUS_CODES:
        if task.completed_at is not None:
            task.completed_at = None
            update_fields.append('completed_at')
        if task.is_auto_closed:
            task.is_auto_closed = False
            update_fields.append('is_auto_closed')
    task.save(update_fields=list(dict.fromkeys(update_fields)))
    audit_service.log_event(
        entity=task,
        action_code='paused',
        action_label='Пауза задачи',
        actor=actor,
        message=(
            f'Задача переведена из статуса «{old_status.name}» '
            f'в «{waiting.name}».'
        ),
        metadata={
            'from_status_code': old_status_code,
            'to_status_code': waiting.code,
        },
        property_obj=task.property,
        request_obj=task.request,
        deal_obj=task.deal,
    )
    return task


class RegisterView(APIView):
    """Регистрация клиента."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = serializers.RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            pending = email_verification.issue_pending_registration(
                serializer.validated_data,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                'Email verification code was not sent to %s: %s',
                serializer.validated_data.get('email'),
                exc,
            )
            return Response(
                {
                    'email': [
                        'Не удалось отправить код подтверждения. '
                        'Проверьте email и попробуйте позже.',
                    ],
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                'verification_token': pending['token'],
                'email': serializer.validated_data['email'],
                'email_verification_required': True,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class VerifyEmailView(APIView):
    """Подтверждение email по коду из письма."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = serializers.EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pending_data = email_verification.consume_pending_registration(
            serializer.validated_data['token'],
            serializer.validated_data['code'],
        )
        if not pending_data:
            raise ValidationError({'code': 'Неверный или просроченный код.'})
        register_serializer = serializers.RegisterSerializer(data=pending_data)
        register_serializer.is_valid(raise_exception=True)
        user = register_serializer.save()
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified', 'updated_at'])
        return Response(serializers.UserSerializer(user).data)


class ResendEmailVerificationView(APIView):
    """Повторная отправка кода подтверждения email."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = serializers.EmailVerificationResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sent = email_verification.resend_pending_code(
            serializer.validated_data['token'],
        )
        if not sent:
            raise ValidationError({'token': 'Регистрация не найдена или код истёк.'})
        return Response({'detail': 'Код отправлен повторно.'})


class LoginView(TokenObtainPairView):
    """Получение пары токенов ``access`` / ``refresh``."""
    permission_classes = [AllowAny]
    serializer_class = serializers.EmailTokenObtainPairSerializer


class MeView(APIView):
    """Информация о текущем пользователе."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serializers.UserSerializer(request.user).data)


class OperationTypeViewSet(viewsets.ModelViewSet):
    queryset = models.OperationType.objects.all()
    serializer_class = serializers.OperationTypeSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class PropertyStatusViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyStatus.objects.all()
    serializer_class = serializers.PropertyStatusSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class RequestStatusViewSet(viewsets.ModelViewSet):
    queryset = models.RequestStatus.objects.exclude(code='closed').order_by('id')
    serializer_class = serializers.RequestStatusSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class DealStatusViewSet(viewsets.ModelViewSet):
    queryset = models.DealStatus.objects.all()
    serializer_class = serializers.DealStatusSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class TaskStatusViewSet(viewsets.ModelViewSet):
    queryset = models.TaskStatus.objects.all()
    serializer_class = serializers.TaskStatusSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class UserRoleViewSet(viewsets.ModelViewSet):
    """Справочник ролей сотрудников."""
    queryset = models.UserRole.objects.all()
    serializer_class = serializers.UserRoleSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class PropertyTypeViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyType.objects.all()
    serializer_class = serializers.PropertyTypeSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class BuildingMaterialViewSet(viewsets.ModelViewSet):
    queryset = models.BuildingMaterial.objects.all()
    serializer_class = serializers.BuildingMaterialSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class BathroomTypeViewSet(viewsets.ModelViewSet):
    queryset = models.BathroomType.objects.all()
    serializer_class = serializers.BathroomTypeSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class RenovationTypeViewSet(viewsets.ModelViewSet):
    queryset = models.RenovationType.objects.all()
    serializer_class = serializers.RenovationTypeSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class CommercialPropertyTypeViewSet(viewsets.ModelViewSet):
    queryset = models.CommercialPropertyType.objects.all()
    serializer_class = serializers.CommercialPropertyTypeSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class AmenityViewSet(viewsets.ModelViewSet):
    queryset = models.Amenity.objects.all()
    serializer_class = serializers.AmenitySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class ViewingStatusSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = models.ViewingStatus
        fields = ['id', 'code', 'name']


class ViewingStatusViewSet(viewsets.ModelViewSet):
    queryset = models.ViewingStatus.objects.all()
    serializer_class = ViewingStatusSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class TaskPriorityViewSet(viewsets.ModelViewSet):
    queryset = models.TaskPriority.objects.all()
    serializer_class = serializers.TaskPrioritySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class TaskTypeViewSet(viewsets.ModelViewSet):
    queryset = models.TaskType.objects.all()
    serializer_class = serializers.TaskTypeSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class ClientKindViewSet(viewsets.ModelViewSet):
    queryset = models.ClientKind.objects.all()
    serializer_class = serializers.ClientKindSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class ContactMethodViewSet(viewsets.ModelViewSet):
    queryset = models.ContactMethod.objects.all()
    serializer_class = serializers.ContactMethodSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class ContractStatusViewSet(viewsets.ModelViewSet):
    queryset = models.ContractStatus.objects.all()
    serializer_class = serializers.ContractStatusSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class UserTypeViewSet(viewsets.ModelViewSet):
    queryset = models.UserType.objects.all()
    serializer_class = serializers.UserTypeSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class CityViewSet(viewsets.ModelViewSet):
    queryset = models.City.objects.all()
    serializer_class = serializers.CitySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'region']


class StreetViewSet(viewsets.ModelViewSet):
    queryset = models.Street.objects.select_related('city').all()
    serializer_class = serializers.StreetSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        city_id = self.request.query_params.get('city')
        if city_id:
            qs = qs.filter(city_id=city_id)
        return qs


class HouseViewSet(viewsets.ModelViewSet):
    queryset = models.House.objects.select_related('street').all()
    serializer_class = serializers.HouseSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        street_id = self.request.query_params.get('street')
        if street_id:
            qs = qs.filter(street_id=street_id)
        return qs


class AddressViewSet(viewsets.ModelViewSet):
    queryset = models.House.objects.select_related('street__city').all()
    serializer_class = serializers.AddressSerializer
    permission_classes = [IsEmployeeOrReadOnly]


class DadataSuggestAddressView(APIView):
    """Подсказки адресов через DaData."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query or len(query) < 2:
            return Response({'results': []})
        try:
            count = int(request.query_params.get('count', 10))
        except ValueError:
            count = 10
        try:
            client = DadataClient()
            results = client.suggest_address(query, count=count)
        except Exception as exc:  # pragma: no cover
            return Response(
                {'detail': 'Сервис подсказок адресов временно недоступен.',
                 'error': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'results': results})


class UserViewSet(viewsets.ModelViewSet):
    """Пользователи системы."""
    queryset = User.objects.select_related('role').order_by('username', 'id')
    serializer_class = serializers.UserSerializer
    permission_classes = [IsEmployee]
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'username',
        'email',
        'phone',
        'client_profile__first_name',
        'client_profile__last_name',
        'employee_profile__first_name',
        'employee_profile__last_name',
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        user_type = params.get('user_type')
        if user_type:
            qs = qs.filter(user_type=user_type)
        role_code = params.get('role')
        if role_code:
            qs = qs.filter(role__code=role_code)
        is_superuser = _parse_bool_param(params.get('is_superuser'))
        if is_superuser is not None:
            qs = qs.filter(is_superuser=is_superuser)
        is_active = _parse_bool_param(params.get('is_active'))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return qs

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update',
                           'destroy', 'assign_role'}:
            return [IsAdminOrManager()]
        return super().get_permissions()

    @staticmethod
    def _profile_names_for(target):
        profile = None
        if hasattr(target, 'client_profile'):
            profile = target.client_profile
        elif hasattr(target, 'employee_profile'):
            profile = target.employee_profile

        username = (target.username or '').strip()[:50] or 'user'
        if profile is None:
            return {
                'first_name': username,
                'last_name': username,
            }

        names = {
            'first_name': (profile.first_name or username)[:50],
            'last_name': (profile.last_name or username)[:50],
        }
        return names

    def _ensure_profile_for_user_type(self, target, user_type):
        names = self._profile_names_for(target)
        if user_type == 'employee' and not hasattr(target, 'employee_profile'):
            models.EmployeeProfile.objects.create(user=target, **names)
        if user_type == 'client' and not hasattr(target, 'client_profile'):
            models.ClientProfile.objects.create(
                user=target,
                client_kind=models.ClientProfile.CLIENT_KIND_INDIVIDUAL,
                **names,
            )

    @action(
        detail=False,
        methods=['get'],
        url_path='export',
        permission_classes=[IsAdminOrManager],
    )
    def export(self, request):
        """Экспорт реестра пользователей в CSV, JSON или XLSX."""
        export_format = (
            request.query_params.get('export_format')
            or request.query_params.get('format')
            or 'csv'
        )
        queryset = self.filter_queryset(self.get_queryset())
        return data_exchange.export_users(queryset, export_format, user=request.user)

    @action(detail=True, methods=['post'], url_path='assign_role')
    def assign_role(self, request, pk=None):
        """Назначить тип учётной записи и роль."""
        target = self.get_object()
        serializer = serializers.UserRoleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            requested_user_type = data.get('user_type', target.user_type)
            target.user_type = requested_user_type

            if requested_user_type == 'client':
                target.role = None
            elif 'role' in data:
                target.role = data['role']

            if 'is_active' in data:
                target.is_active = data['is_active']

            target.is_staff = bool(
                target.is_superuser or requested_user_type == 'employee'
            )
            target.save()
            self._ensure_profile_for_user_type(target, requested_user_type)
        return Response(serializers.UserSerializer(target).data)

    @action(detail=False, methods=['get'], url_path='me/workload',
            permission_classes=[IsAuthenticated])
    def my_workload(self, request):
        """Сводка текущей загрузки сотрудника."""
        if not request.user.is_employee:
            return Response({
                'active_tasks': 0,
                'in_progress_tasks': 0,
                'active_requests': 0,
                'max_active_tasks': business_rules.MAX_ACTIVE_TASKS,
                'max_in_progress_tasks':
                    business_rules.MAX_IN_PROGRESS_TASKS,
                'max_active_requests':
                    business_rules.MAX_ACTIVE_REQUESTS,
                'can_take_request': False,
                'can_take_task': False,
                'can_start_task': False,
            })
        return Response(business_rules.snapshot_for(request.user).as_dict())

    @action(detail=True, methods=['get'], url_path='workload',
            permission_classes=[IsAdminOrManager])
    def user_workload(self, request, pk=None):
        """Нагрузка конкретного сотрудника — только для менеджеров/админов."""
        target = self.get_object()
        if not target.is_employee:
            return Response(
                {'detail': 'Учитывается только загрузка сотрудников.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(business_rules.snapshot_for(target).as_dict())


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    queryset = models.EmployeeProfile.objects.select_related('user').order_by('id')
    serializer_class = serializers.EmployeeProfileSerializer
    permission_classes = [IsEmployee]
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'user__username',
        'user__email',
        'user__phone',
        'first_name',
        'last_name',
        'position',
        'internal_phone',
    ]


class ClientProfileViewSet(viewsets.ModelViewSet):
    queryset = models.ClientProfile.objects.select_related(
        'user',
        'individual_details',
        'company_details',
    ).order_by('id')
    serializer_class = serializers.ClientProfileSerializer
    permission_classes = [IsOwnClientProfileOrEmployee]
    filter_backends = [filters.SearchFilter]
    search_fields = [
        'user__username',
        'user__email',
        'user__phone',
        'first_name',
        'last_name',
        'middle_name',
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(user=user)
        return qs


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = models.Property.objects.select_related(
        'operation_type', 'status', 'house__street__city',
        'house__building_details', 'details', 'commercial_details',
    ).prefetch_related(
        'photos',
        'owners__client_profile__user',
        'amenities__amenity',
        'documents',
        'price_history',
    ).all()
    serializer_class = serializers.PropertySerializer
    permission_classes = [IsEmployeeOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['=id', 'title', 'description']
    ordering_fields = ['price', 'created_at', 'area_total']

    def get_permissions(self):
        if self.action == 'create':
            return [IsClientOrAdminOrManager()]
        if self.action in {'update', 'partial_update', 'destroy', 'upload_photo'}:
            return [IsAuthenticated()]
        if self.action == 'change_status':
            return [IsEmployee()]
        if self.action == 'bulk_archive':
            return [IsEmployee()]
        if self.action in {'import_csv', 'moderation', 'approve', 'reject'}:
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params
        public_status_codes = {'active', 'reserved', 'sold', 'rented'}
        if user.is_authenticated and user.is_client:
            if params.get('owner') == 'me':
                qs = qs.filter(owners__client_profile__user=user).distinct()
            elif self.action == 'list':
                qs = qs.filter(status__code__in=public_status_codes)
            elif self.action == 'retrieve':
                qs = qs.filter(
                    Q(status__code__in=public_status_codes)
                    | Q(owners__client_profile__user=user),
                )
            if self.action not in {'list', 'retrieve'} and params.get('owner') != 'me':
                qs = qs.filter(owners__client_profile__user=user).distinct()
        elif self.action == 'list' and params.get('owner') != 'me' and not params.get('status'):
            qs = qs.filter(status__code__in=public_status_codes)
        if params.get('owner') == 'me' and user.is_authenticated:
            qs = qs.filter(owners__client_profile__user=user).distinct()
        return _apply_property_filters(qs, params)

    @staticmethod
    def _fetch_twogis_photos(property_obj) -> int:
        """Fetch 2GIS enrichment and create photos when the object has none."""
        import logging

        _log = logging.getLogger(__name__)

        try:
            address = property_obj.address
            if address is None:
                return 0

            address_str = str(address).strip()
            if not address_str or address_str == 'None':
                return 0

            client = TwoGisClient()
            if not client.api_key:
                return 0

            city_name = ''
            try:
                city_name = address.house.street.city.name
            except AttributeError:
                pass

            info = client.search_by_address(address_str, city=city_name)
            if not info:
                return 0

            created = apply_property_enrichment(property_obj, info)
            if created:
                _log.info(
                    '2GIS: added %d photo cards for property pk=%s',
                    created, property_obj.pk,
                )
            return created

        except Exception as exc:  # noqa: BLE001
            import logging as _logging
            _logging.getLogger(__name__).warning(
                '2GIS enrichment for property pk=%s failed: %s',
                property_obj.pk, exc,
            )
            return 0

    def perform_create(self, serializer):
        if self.request.user.is_employee and not self.request.user.is_admin_or_manager:
            raise ValidationError(
                {'detail': 'Сотрудникам нельзя создавать объекты. Создание доступно только клиентам и руководителям.'},
            )
        save_kwargs = {}
        if self.request.user.is_client:
            pending_status = models.PropertyStatus.objects.filter(code='pending').first()
            save_kwargs['owner'] = self.request.user
            if pending_status is not None:
                save_kwargs['status'] = pending_status
        property_obj = serializer.save(**save_kwargs)
        audit_service.log_event(
            entity=property_obj,
            action_code='created',
            action_label='Создание объекта',
            actor=self.request.user,
            message='Объект недвижимости создан.',
            metadata={
                'status_code': getattr(property_obj.status, 'code', None),
                'operation_type_id': property_obj.operation_type_id,
            },
        )
        # Автоматически подгружаем фото из 2GIS Static Maps при создании
        self._fetch_twogis_photos(property_obj)

    @action(detail=False, methods=['get'], url_path='moderation')
    def moderation(self, request):
        qs = self.get_queryset().filter(status__code='pending')
        return Response(serializers.PropertySerializer(
            qs.select_related(
                'operation_type', 'status', 'house__street__city',
                'house__building_details', 'details', 'commercial_details',
            ).prefetch_related(
                'photos', 'owners__client_profile__user', 'amenities__amenity',
            ),
            many=True, context={'request': request}
        ).data)

    def _set_status_by_code(self, property_obj, status_code: str, *, request, action_code: str, action_label: str):
        next_status = models.PropertyStatus.objects.filter(code=status_code).first()
        if next_status is None:
            return Response(
                {'detail': f'Статус "{status_code}" не настроен.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if property_obj.status_id == next_status.pk:
            return Response(serializers.PropertySerializer(
                property_obj, context={'request': request}).data)
        transition_error = business_rules.property_status_transition_error(
            property_obj,
            next_status,
        )
        if transition_error:
            return Response({'detail': transition_error},
                            status=status.HTTP_400_BAD_REQUEST)
        previous_status = property_obj.status
        property_obj.status = next_status
        property_obj.save(update_fields=['status', 'updated_at'])
        models.PropertyStatusHistory.objects.create(
            property=property_obj,
            old_status=previous_status,
            new_status=next_status,
            changed_by=request.user,
        )
        audit_service.log_event(
            entity=property_obj,
            action_code=action_code,
            action_label=action_label,
            actor=request.user,
            message=(
                f'Объект переведён из статуса «{previous_status.name}» '
                f'в «{next_status.name}» после проверки менеджером.'
            ),
            metadata={
                'from_status_id': previous_status.pk,
                'from_status_code': getattr(previous_status, 'code', None),
                'to_status_id': next_status.pk,
                'to_status_code': next_status.code,
                'moderation_note': request.data.get('note', '') or '',
            },
        )
        return Response(serializers.PropertySerializer(
            property_obj, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """Одобрить клиентский объект и вывести его в общий каталог."""
        return self._set_status_by_code(
            self.get_object(),
            'active',
            request=request,
            action_code='moderation_approved',
            action_label='Одобрение объекта',
        )

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Отклонить клиентский объект после проверки."""
        return self._set_status_by_code(
            self.get_object(),
            'archived',
            request=request,
            action_code='moderation_rejected',
            action_label='Отклонение объекта',
        )

    def perform_update(self, serializer):
        changed_fields = sorted(serializer.validated_data.keys())
        before_snapshot = audit_service.snapshot_fields(
            serializer.instance,
            changed_fields,
        )
        old_price = serializer.instance.price
        property_obj = serializer.save()
        new_price = property_obj.price
        if 'price' in changed_fields and old_price != new_price:
            models.PropertyPriceHistory.objects.create(
                property=property_obj,
                old_price=old_price,
                new_price=new_price,
                changed_by=self.request.user,
            )
        field_changes = audit_service.diff_field_snapshots(
            before_snapshot,
            audit_service.snapshot_fields(property_obj, changed_fields),
        )
        audit_service.log_event(
            entity=property_obj,
            action_code='updated',
            action_label='Редактирование объекта',
            actor=self.request.user,
            message='Карточка объекта обновлена.',
            metadata={
                'changed_fields': changed_fields,
                'field_changes': field_changes,
            },
        )

    def perform_destroy(self, instance):
        audit_service.log_event(
            entity=instance,
            action_code='deleted',
            action_label='Удаление объекта',
            actor=self.request.user,
            message='Объект недвижимости удалён.',
        )
        try:
            super().perform_destroy(instance)
        except ProtectedError:
            raise ValidationError(
                detail='Невозможно удалить объект: к нему привязаны активные заявки, сделки или просмотры. '
                       'Сначала удалите или переназначьте связанные записи.'
            )

    @action(
        detail=False,
        methods=['post'],
        url_path='import-csv',
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[IsEmployee],
    )
    def import_csv(self, request):
        """Импорт каталога объектов из CSV или XLSX."""
        upload = request.FILES.get('file')
        if upload is None:
            return Response(
                {'detail': 'Нужно передать файл в поле file.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            summary = data_exchange.import_properties(
                upload,
                actor=request.user,
                request=request,
            )
        return Response(summary, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bulk-archive')
    def bulk_archive(self, request):
        serializer = serializers.BulkIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        archived_status = models.PropertyStatus.objects.filter(
            code='archived',
        ).first()
        if archived_status is None:
            return Response(
                {'detail': 'Статус архива не настроен.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        requested_ids = serializer.validated_data['ids']
        properties = list(
            self.get_queryset()
            .filter(pk__in=requested_ids)
            .select_related('status', 'operation_type')
        )
        found_ids = {property_obj.pk for property_obj in properties}
        archived_count = 0
        errors = []

        for property_obj in properties:
            transition_error = business_rules.property_status_transition_error(
                property_obj,
                archived_status,
            )
            if transition_error:
                errors.append({
                    'id': property_obj.pk,
                    'detail': transition_error,
                })
                continue
            if property_obj.status_id == archived_status.pk:
                continue

            previous_status = property_obj.status
            property_obj.status = archived_status
            property_obj.save(update_fields=['status', 'updated_at'])
            models.PropertyStatusHistory.objects.create(
                property=property_obj,
                old_status=previous_status,
                new_status=archived_status,
                changed_by=request.user,
            )
            audit_service.log_event(
                entity=property_obj,
                action_code='bulk_archived',
                action_label='Массовое архивирование объекта',
                actor=request.user,
                message=(
                    f'Объект переведён из статуса «{previous_status.name}» '
                    'в архив.'
                ),
                metadata={
                    'from_status_id': previous_status.pk,
                    'from_status_code': getattr(previous_status, 'code', None),
                    'to_status_id': archived_status.pk,
                    'to_status_code': archived_status.code,
                    'bulk': True,
                },
            )
            archived_count += 1

        not_found_ids = [
            property_id for property_id in requested_ids
            if property_id not in found_ids
        ]
        return Response({
            'requested': len(requested_ids),
            'processed': len(properties),
            'archived': archived_count,
            'errors': errors,
            'not_found_ids': not_found_ids,
        })

    @action(detail=True, methods=['post'], url_path='change_status')
    def change_status(self, request, pk=None):
        """Смена статуса объекта с записью в историю."""
        property_obj = self.get_object()
        new_status_id = request.data.get('status_id')
        if not new_status_id:
            return Response({'detail': 'Не указан статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        next_status = models.PropertyStatus.objects.filter(pk=new_status_id).first()
        if not next_status:
            return Response({'detail': 'Неизвестный статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if property_obj.status_id == next_status.pk:
            return Response(serializers.PropertySerializer(
                property_obj, context={'request': request}).data)
        transition_error = business_rules.property_status_transition_error(
            property_obj, next_status,
        )
        if transition_error:
            return Response({'detail': transition_error},
                            status=status.HTTP_400_BAD_REQUEST)
        previous_status = property_obj.status
        property_obj.status = next_status
        property_obj.save(update_fields=['status', 'updated_at'])
        models.PropertyStatusHistory.objects.create(
            property=property_obj,
            old_status=previous_status,
            new_status=next_status,
            changed_by=request.user,
        )
        audit_service.log_event(
            entity=property_obj,
            action_code='status_changed',
            action_label='Смена статуса',
            actor=request.user,
            message=(
                f'Статус объекта изменён с «{previous_status.name}» '
                f'на «{next_status.name}».'
            ),
            metadata={
                'from_status_id': previous_status.pk,
                'from_status_code': getattr(previous_status, 'code', None),
                'to_status_id': next_status.pk,
                'to_status_code': next_status.code,
            },
        )
        return Response(serializers.PropertySerializer(
            property_obj, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """История смен статусов объекта."""
        property_obj = self.get_object()
        qs = property_obj.status_history.select_related(
            'old_status', 'new_status', 'changed_by',
        )
        return Response(
            serializers.PropertyStatusHistorySerializer(qs, many=True).data
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='upload_photo',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        permission_classes=[IsAdminOrManager],
    )
    def upload_photo(self, request, pk=None):
        """Загрузить фото объекта."""
        property_obj = self.get_object()
        if request.user.is_employee and not request.user.is_admin_or_manager:
            return Response(
                {'detail': 'Сотрудникам нельзя загружать фото к объектам.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if request.user.is_client and not property_obj.is_owned_by(request.user):
            return Response(
                {'detail': 'Можно загружать фото только к своему объекту.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        image = request.FILES.get('image')
        url = request.data.get('url')
        if not image and not url:
            return Response(
                {'detail': 'Нужно передать файл image или ссылку url.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_first = not property_obj.photos.exists()
        photo = models.PropertyPhoto.objects.create(
            property=property_obj,
            url=url or '',
            caption=request.data.get('caption', '') or '',
            order=property_obj.photos.count(),
        )
        if image:
            from django.core.files.storage import default_storage
            saved_path = default_storage.save(
                f'property-photos/{timezone.now():%Y/%m}/{getattr(image, "name", "") or "property-photo"}',
                image,
            )
            photo.url = default_storage.url(saved_path)
        wants_cover = str(request.data.get('is_cover', '')).lower() in {'1', 'true', 'yes'}
        photo.order = 0 if (is_first or wants_cover) else 1
        photo.save(update_fields=['url', 'order'])
        if is_first or wants_cover:
            self._normalize_cover(property_obj.pk, preferred_photo_id=photo.pk)
        return Response(
            serializers.PropertyPhotoSerializer(
                photo, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class PropertyPhotoViewSet(viewsets.ModelViewSet):
    """Фото объекта и действия по альбому."""
    queryset = models.PropertyPhoto.objects.all()
    serializer_class = serializers.PropertyPhotoSerializer
    permission_classes = [IsClientOrAdminOrManager]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @staticmethod
    def _normalize_cover(property_id, preferred_photo_id=None):
        photos = models.PropertyPhoto.objects.filter(property_id=property_id)
        if not photos.exists():
            return

        cover = None
        if preferred_photo_id is not None:
            cover = photos.filter(pk=preferred_photo_id).first()
        if cover is None:
            cover = photos.order_by('order', '-uploaded_at', 'pk').first()
        if cover is None:
            return

        photos.exclude(pk=cover.pk).update(order=1)
        update_fields = []
        if cover.order != 0:
            cover.order = 0
            update_fields.append('order')
        if cover.is_hidden:
            cover.is_hidden = False
            update_fields.append('is_hidden')
        if update_fields:
            cover.save(update_fields=update_fields)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            if user.is_client:
                qs = qs.filter(property__owners__client_profile__user=user).distinct()
            elif user.is_employee and not user.is_admin_or_manager:
                qs = qs.none()
        prop = self.request.query_params.get('property')
        if prop:
            qs = qs.filter(property_id=prop)
        if self.request.query_params.get('show_hidden') == '0':
            qs = qs.filter(is_hidden=False)
        return qs

    def perform_create(self, serializer):
        property_obj = serializer.validated_data['property']
        user = self.request.user
        if user.is_client and not property_obj.is_owned_by(user):
            raise ValidationError(
                {'detail': 'Можно загружать фото только к своему объекту.'},
            )
        if user.is_employee and not user.is_admin_or_manager:
            raise ValidationError(
                {'detail': 'Сотрудникам нельзя загружать фото к объектам.'},
            )
        has_existing = models.PropertyPhoto.objects.filter(
            property=property_obj,
        ).exists()
        wants_cover = bool(serializer.validated_data.get('is_cover'))
        should_prefer = wants_cover or not has_existing

        save_kwargs = {}
        if should_prefer:
            save_kwargs['is_hidden'] = False
            save_kwargs['order'] = 0
        else:
            save_kwargs['order'] = 1
        photo = serializer.save(**save_kwargs)
        self._normalize_cover(
            property_obj.pk,
            preferred_photo_id=photo.pk if should_prefer else None,
        )

    def perform_update(self, serializer):
        photo = self.get_object()
        property_obj = serializer.validated_data.get('property', photo.property)
        wants_cover = serializer.validated_data.get('is_cover', photo.is_cover)
        is_cover_specified = 'is_cover' in serializer.validated_data

        save_kwargs = {}
        if wants_cover:
            save_kwargs['is_hidden'] = False
            save_kwargs['order'] = 0
        elif is_cover_specified:
            save_kwargs['order'] = 1
        updated = serializer.save(**save_kwargs)
        self._normalize_cover(
            property_obj.pk,
            preferred_photo_id=updated.pk if wants_cover else None,
        )

    def perform_destroy(self, instance):
        property_id = instance.property_id
        super().perform_destroy(instance)
        self._normalize_cover(property_id)

    @action(detail=True, methods=['post'], url_path='set_cover')
    def set_cover(self, request, pk=None):
        """Сделать выбранное фото обложкой объекта."""
        photo = self.get_object()
        models.PropertyPhoto.objects.filter(property_id=photo.property_id).exclude(pk=photo.pk).update(order=1)
        photo.order = 0
        photo.is_hidden = False  # обложка не может быть скрытой
        photo.save(update_fields=['order', 'is_hidden'])
        return Response(serializers.PropertyPhotoSerializer(
            photo, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='toggle_hidden')
    def toggle_hidden(self, request, pk=None):
        """Скрыть/показать фото. Обложку скрыть нельзя."""
        photo = self.get_object()
        if photo.is_cover and not photo.is_hidden:
            return Response(
                {'detail': 'Нельзя скрыть фото-обложку. '
                           'Сначала назначьте обложкой другое фото.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        photo.is_hidden = not photo.is_hidden
        photo.save(update_fields=['is_hidden'])
        return Response(serializers.PropertyPhotoSerializer(
            photo, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """
        Массовая перестановка порядка. Тело: ``{"order": [id1, id2, ...]}``.
        Все фото должны принадлежать одному объекту.
        """
        order = request.data.get('order') or []
        if not isinstance(order, list) or not order:
            return Response({'detail': 'Нужно поле order: [id,...]'},
                            status=status.HTTP_400_BAD_REQUEST)
        photos = list(self.get_queryset().filter(pk__in=order))
        if len({p.property_id for p in photos}) > 1:
            return Response({'detail': 'Фото разных объектов.'},
                            status=status.HTTP_400_BAD_REQUEST)
        by_id = {p.pk: p for p in photos}
        for idx, pid in enumerate(order):
            p = by_id.get(pid)
            if p is None:
                continue
            if p.order != idx:
                p.order = idx
                p.save(update_fields=['order'])
        return Response({'detail': 'Порядок обновлён.'})


class PropertyDocumentViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyDocument.objects.select_related('verified_by').all()
    serializer_class = serializers.PropertyDocumentSerializer
    permission_classes = [IsEmployee]

    def get_queryset(self):
        qs = super().get_queryset()
        property_id = self.request.query_params.get('property')
        if property_id:
            qs = qs.filter(property_id=property_id)
        return qs

    def perform_create(self, serializer):
        doc = serializer.save()
        if doc.is_verified and not doc.verified_by_id:
            doc.verified_by = self.request.user
        if doc.is_verified and not doc.verified_at:
            doc.verified_at = timezone.now()
        if doc.is_verified:
            doc.save(update_fields=['verified_by', 'verified_at'])

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Отметить документ как проверенный."""
        doc = self.get_object()
        doc.is_verified = True
        doc.verified_by = request.user
        doc.verified_at = timezone.now()
        doc.save()
        return Response(serializers.PropertyDocumentSerializer(doc).data)


class PropertyPriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.PropertyPriceHistory.objects.select_related('changed_by', 'property').all()
    serializer_class = serializers.PropertyPriceHistorySerializer
    permission_classes = [IsEmployee]

    def get_queryset(self):
        qs = super().get_queryset()
        property_id = self.request.query_params.get('property')
        if property_id:
            qs = qs.filter(property_id=property_id)
        return qs


class RequestViewSet(viewsets.ModelViewSet):
    """Заявки клиентов."""
    queryset = models.Request.objects.select_related(
        'client_profile__user', 'employee_profile__user',
        'operation_type', 'status', 'property',
    ).prefetch_related(
        'matches__property', 'matches__employee_profile__user', 'matches__confirmed_by',
    ).all()
    serializer_class = serializers.RequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['created_at', 'updated_at']
    search_fields = [
        '=id',
        'description',
        'client_profile__user__username',
        'client_profile__user__email',
        'client_profile__user__phone',
        'client_profile__first_name',
        'client_profile__last_name',
        'employee_profile__user__username',
        'employee_profile__first_name',
        'employee_profile__last_name',
        'property__title',
    ]

    def get_permissions(self):
        if self.action in {
            'update', 'partial_update', 'destroy',
            'bulk_close',
            'close', 'take', 'attach_property',
            'detach_property', 'confirm_property', 'accept_match',
        }:
            return [IsEmployee()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(client_profile__user=user)
        elif user.is_authenticated and user.is_employee and not user.is_admin_or_manager:
            mutable_actions = {
                'update', 'partial_update', 'destroy',
                'bulk_close',
                'close', 'attach_property', 'detach_property',
                'confirm_property', 'accept_match',
            }
            if self.action in mutable_actions:
                qs = qs.filter(employee_profile__user=user)
            elif self.action == 'take':
                qs = qs.filter(
                    _employee_visible_requests_q(user),
                    status__code__in=models.Request.ACTIVE_STATUS_CODES,
                )
            else:
                qs = qs.filter(_employee_visible_requests_q(user))

        params = self.request.query_params
        if params.get('client'):
            qs = qs.filter(client_profile__user_id=params['client'])
        if params.get('agent'):
            value = params['agent']
            if value == 'me' and user.is_employee:
                qs = qs.filter(employee_profile__user=user)
            elif value != 'me':
                qs = qs.filter(employee_profile__user_id=value)
        if params.get('property'):
            qs = qs.filter(property_id=params['property'])
        if params.get('operation_type'):
            qs = qs.filter(operation_type_id=params['operation_type'])
        if params.get('status'):
            qs = qs.filter(status_id=params['status'])
        if params.get('status_code'):
            codes = [c.strip() for c in params['status_code'].split(',')
                     if c.strip()]
            qs = qs.filter(
                status__code__in=models.Request.expand_status_filter_codes(
                    codes,
                ),
            )
        qs = _apply_date_range_filter(
            qs,
            params,
            field_name='created_at',
            use_date_lookup=True,
        )
        scope = params.get('scope')
        if scope == 'unassigned' and user.is_employee:
            qs = qs.filter(employee_profile__isnull=True)
        elif scope == 'mine' and user.is_employee:
            qs = qs.filter(employee_profile__user=user)
        return qs

    def perform_create(self, serializer):
        """Подставить клиента из сессии при самоподаче заявки."""
        serializer.instance = request_lifecycle.create_request_from_serializer(
            serializer,
            actor=self.request.user,
        )

    def perform_update(self, serializer):
        if serializer.instance.is_terminal:
            raise ValidationError(
                {'detail': 'Нельзя редактировать закрытую заявку.'},
            )
        previous_agent_id = serializer.instance.agent_id
        changed_fields = sorted(serializer.validated_data.keys())
        before_snapshot = audit_service.snapshot_fields(
            serializer.instance,
            changed_fields,
        )
        with transaction.atomic():
            request_obj = serializer.save()
            if request_obj.agent_id:
                request_obj = request_lifecycle.sync_request_assignment(
                    request_obj,
                    previous_agent_id=previous_agent_id,
                    actor=self.request.user,
                ).request
            field_changes = audit_service.diff_field_snapshots(
                before_snapshot,
                audit_service.snapshot_fields(request_obj, changed_fields),
            )
            audit_service.log_event(
                entity=request_obj,
                action_code='updated',
                action_label='Редактирование заявки',
                actor=self.request.user,
                message='Карточка заявки обновлена.',
                metadata={
                    'changed_fields': changed_fields,
                    'field_changes': field_changes,
                },
                property_obj=request_obj.property,
            )
        serializer.instance = request_obj

    def perform_destroy(self, instance):
        if instance.is_terminal:
            raise ValidationError(
                {'detail': 'Нельзя удалить закрытую заявку.'},
            )
        audit_service.log_event(
            entity=instance,
            action_code='deleted',
            action_label='Удаление заявки',
            actor=self.request.user,
            message='Заявка удалена.',
            property_obj=instance.property,
        )
        super().perform_destroy(instance)

    @action(
        detail=False,
        methods=['get'],
        url_path='export',
        permission_classes=[IsAdminOrManager],
    )
    def export(self, request):
        """Экспорт списка заявок в CSV, JSON или XLSX."""
        export_format = (
            request.query_params.get('export_format')
            or request.query_params.get('format')
            or 'csv'
        )
        queryset = self.filter_queryset(self.get_queryset())
        return data_exchange.export_requests(
            queryset,
            export_format,
            user=request.user,
            title=data_exchange._export_title(
                data_exchange.REQUEST_EXPORT_DEFINITION,
                request.user,
            ),
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Закрыть заявку и при необходимости создать сделку."""
        serializer = serializers.RequestCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = serializer.validated_data['outcome']
        try:
            result = request_lifecycle.close_request(
                self.get_object(),
                outcome=outcome,
                actor=request.user,
            )
        except ValidationError as exc:
            return Response(
                _validation_error_payload(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = serializers.RequestSerializer(result.request).data
        payload['outcome'] = outcome
        payload['detail'] = {
            'completed': (
                'Заявка завершена.'
                if result.deal is None else
                'Заявка завершена, сделка создана.'
            ),
            'cancelled': 'Заявка отменена.',
            'rejected': 'Заявка отклонена.',
            'lost': 'Заявка помечена как потерянная.',
        }[outcome]
        if result.deal is not None:
            payload['deal'] = serializers.DealSerializer(result.deal).data
        return Response(payload)

    @action(detail=False, methods=['post'], url_path='bulk-close')
    def bulk_close(self, request):
        serializer = serializers.RequestBulkCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_ids = serializer.validated_data['ids']
        outcome = serializer.validated_data['outcome']

        requests_qs = list(
            self.get_queryset()
            .filter(pk__in=requested_ids)
            .select_related('status', 'client_profile__user', 'employee_profile__user', 'operation_type')
        )
        found_ids = {request_obj.pk for request_obj in requests_qs}
        closed_count = 0
        deals_created = 0
        errors = []

        for request_obj in requests_qs:
            try:
                result = request_lifecycle.close_request(
                    request_obj,
                    outcome=outcome,
                    actor=request.user,
                )
            except ValidationError as exc:
                payload = _validation_error_payload(exc)
                errors.append({
                    'id': request_obj.pk,
                    'detail': payload.get('detail', 'Не удалось закрыть заявку.'),
                })
                continue
            closed_count += 1
            if result.deal is not None:
                deals_created += 1
            # Отдельно фиксируем факт массовой операции (помимо обычного "closed").
            audit_service.log_event(
                entity=result.request,
                action_code='bulk_closed',
                action_label='Массовое закрытие заявки',
                actor=request.user,
                message='Заявка закрыта через массовую операцию.',
                metadata={
                    'bulk': True,
                    'outcome': outcome,
                },
                property_obj=result.request.property,
                deal_obj=result.deal,
            )

        not_found_ids = [
            request_id for request_id in requested_ids
            if request_id not in found_ids
        ]
        return Response({
            'requested': len(requested_ids),
            'processed': len(requests_qs),
            'closed': closed_count,
            'outcome': outcome,
            'deals_created': deals_created,
            'errors': errors,
            'not_found_ids': not_found_ids,
        })

    @action(detail=True, methods=['post'])
    def take(self, request, pk=None):
        """Взять заявку в работу."""
        if not request.user.is_employee:
            return Response(
                {'detail': 'Доступно только сотрудникам.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            result = request_lifecycle.take_request(
                self.get_object(),
                actor=request.user,
            )
        except WorkloadLimitExceeded as exc:
            return Response(
                {'detail': exc.detail, 'code': exc.code},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as exc:
            return Response(
                _validation_error_payload(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializers.RequestSerializer(result.request).data)

    @action(detail=True, methods=['post'], url_path='attach_property')
    def attach_property(self, request, pk=None):
        """
        Добавить вариант объекта в подборку по заявке (только сотрудник).

        Ожидает ``property_id`` и опционально ``agent_note``.
        """
        if not request.user.is_employee:
            return Response(
                {'detail': 'Доступно только сотрудникам.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        req = self.get_object()
        property_id = request.data.get('property_id')
        if not property_id:
            return Response({'detail': 'Не указан объект.'},
                            status=status.HTTP_400_BAD_REQUEST)
        match, created = models.RequestPropertyMatch.objects.get_or_create(
            request=req, property_id=property_id,
            defaults={'agent': request.user,
                      'agent_note': request.data.get('agent_note', '')},
        )
        if not created:
            was_rejected = match.is_rejected
            was_confirmed = match.is_confirmed
            update_fields = []
            if match.is_rejected:
                match.is_rejected = False
                update_fields.append('is_rejected')
            if not match.is_offered:
                match.is_offered = True
                update_fields.append('is_offered')
            if was_rejected and was_confirmed:
                match.is_confirmed = False
                match.confirmed_at = None
                match.confirmed_by = None
                update_fields.extend(
                    ['is_confirmed', 'confirmed_at', 'confirmed_by'],
                )
            if request.data.get('agent_note') is not None:
                match.agent_note = request.data['agent_note']
                update_fields.append('agent_note')
            if update_fields:
                match.save(update_fields=update_fields)
        audit_service.log_event(
            entity=req,
            action_code='match_attached',
            action_label='Добавление варианта',
            actor=request.user,
            message=f'В подборку заявки добавлен объект №{match.property_id}.',
            metadata={
                'match_id': match.pk,
                'property_id': match.property_id,
                'created': created,
            },
            property_obj=match.property,
        )
        return Response(
            serializers.RequestPropertyMatchSerializer(match).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='detach_property')
    def detach_property(self, request, pk=None):
        """Удалить вариант из подборки по заявке."""
        if not request.user.is_employee:
            return Response(
                {'detail': 'Доступно только сотрудникам.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        req = self.get_object()
        match_id = request.data.get('match_id')
        match = req.matches.select_related('property').filter(pk=match_id).first()
        if match is None:
            return Response({'detail': 'Вариант не найден.'},
                            status=status.HTTP_404_NOT_FOUND)
        audit_service.log_event(
            entity=req,
            action_code='match_detached',
            action_label='Удаление варианта',
            actor=request.user,
            message=f'Из подборки заявки удалён объект №{match.property_id}.',
            metadata={
                'match_id': match.pk,
                'property_id': match.property_id,
            },
            property_obj=match.property,
        )
        deleted, _ = req.matches.filter(pk=match_id).delete()
        if not deleted:
            return Response({'detail': 'Вариант не найден.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='confirm_property')
    def confirm_property(self, request, pk=None):
        """Подтвердить вариант из подборки."""
        if not request.user.is_employee:
            return Response(
                {'detail': 'Доступно только сотрудникам.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        match_id = request.data.get('match_id')
        if not match_id:
            return Response({'detail': 'Не указан match_id.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result = request_lifecycle.confirm_request_match(
                self.get_object(),
                match_id=match_id,
                actor=request.user,
            )
        except ValidationError as exc:
            payload = _validation_error_payload(exc)
            status_code = (
                status.HTTP_404_NOT_FOUND
                if str(payload.get('detail')) == 'Вариант не найден.'
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(payload, status=status_code)

        return Response({
            'detail': (
                'Вариант уже подтверждён.'
                if result.already_confirmed else
                'Вариант подтверждён. Задачи подбора закрыты, '
                'письмо клиенту поставлено в очередь.'
            ),
            'match': serializers.RequestPropertyMatchSerializer(result.match).data,
        })

    @action(detail=True, methods=['post'], url_path='accept_match')
    def accept_match(self, request, pk=None):
        """Алиас для старого фронтенда."""
        return self.confirm_property(request, pk=pk)


class RequestPropertyMatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Только чтение подборки; модификация — через действия RequestViewSet."""
    queryset = models.RequestPropertyMatch.objects.select_related(
        'property', 'employee_profile__user', 'request__client_profile__user',
        'request__employee_profile__user', 'confirmed_by',
    ).all()
    serializer_class = serializers.RequestPropertyMatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(request__client_profile__user=user)
        elif user.is_authenticated and user.is_employee and not user.is_admin_or_manager:
            qs = qs.filter(_employee_visible_requests_q(user, prefix='request__'))
        request_id = self.request.query_params.get('request')
        if request_id:
            qs = qs.filter(request_id=request_id)
        return qs


class DealViewSet(viewsets.ModelViewSet):
    queryset = models.Deal.objects.select_related(
        'property', 'agent', 'client', 'employee_profile__user', 'operation_type', 'status'
    ).all()
    serializer_class = serializers.DealSerializer
    permission_classes = [IsEmployeeOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['deal_date', 'contract_generated_at', 'price_final']

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, 'action', None) in {'contract', 'regenerate_contract'}:
            qs = qs.prefetch_related(
                'property__owners__client_profile__user',
                'property__owners__client_profile__individual_details',
                'property__owners__client_profile__company_details',
            )
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(client=user)
        elif user.is_authenticated and user.is_employee and not user.is_admin_or_manager:
            qs = qs.filter(agent=user)

        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status_id=params['status'])
        if params.get('status_code'):
            codes = [c.strip() for c in params['status_code'].split(',')
                     if c.strip()]
            qs = qs.filter(status__code__in=codes)
        if params.get('operation_type'):
            qs = qs.filter(operation_type_id=params['operation_type'])
        if params.get('request'):
            qs = qs.filter(request_id=params['request'])
        if params.get('agent'):
            value = params['agent']
            if value == 'me' and user.is_employee:
                qs = qs.filter(agent=user)
            elif value != 'me':
                qs = qs.filter(agent_id=value)
        qs = _apply_date_range_filter(
            qs,
            params,
            field_name='deal_date',
        )
        return qs

    @action(
        detail=False,
        methods=['get'],
        url_path='export',
        permission_classes=[IsAdminOrManager],
    )
    def export(self, request):
        """Экспорт списка сделок в CSV, JSON или XLSX."""
        export_format = (
            request.query_params.get('export_format')
            or request.query_params.get('format')
            or 'csv'
        )
        queryset = self.filter_queryset(self.get_queryset())
        return data_exchange.export_deals(
            queryset,
            export_format,
            user=request.user,
            title=data_exchange._export_title(
                data_exchange.DEAL_EXPORT_DEFINITION,
                request.user,
            ),
        )

    @action(detail=True, methods=['post'], url_path='change_status')
    def change_status(self, request, pk=None):
        """Смена статуса сделки (воронка продаж)."""
        deal = self.get_object()
        status_id = request.data.get('status_id')
        if not status_id:
            return Response({'detail': 'Не указан статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        next_status = models.DealStatus.objects.filter(pk=status_id).first()
        if not next_status:
            return Response({'detail': 'Неизвестный статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if deal.status_id == next_status.pk:
            return Response(serializers.DealSerializer(deal).data)
        transition_error = business_rules.deal_status_transition_error(
            deal, next_status,
        )
        if transition_error:
            return Response({'detail': transition_error},
                            status=status.HTTP_400_BAD_REQUEST)
        previous_status = deal.status
        deal.status = next_status
        deal.save(update_fields=['status'])
        audit_service.log_event(
            entity=deal,
            action_code='status_changed',
            action_label='Смена статуса сделки',
            actor=request.user,
            message=(
                f'Статус сделки изменён с «{getattr(previous_status, "name", "не указан")}» '
                f'на «{next_status.name}».'
            ),
            metadata={
                'from_status_id': getattr(previous_status, 'pk', None),
                'from_status_code': getattr(previous_status, 'code', None),
                'to_status_id': next_status.pk,
                'to_status_code': next_status.code,
            },
            property_obj=deal.property,
            request_obj=deal.request,
        )
        return Response(serializers.DealSerializer(deal).data)

    @action(detail=True, methods=['get'], url_path='contract')
    def contract(self, request, pk=None):
        """Скачать PDF-договор по сделке."""
        deal = self.get_object()
        if not deal.contract_file:
            if deal.contract_status in {'pending', 'processing'}:
                return Response(
                    {
                        'detail': 'Договор формируется в фоновом процессе.',
                        'contract_status': deal.contract_status,
                        'contract_status_display': deal.get_contract_status_display(),
                        'contract_requested_at': deal.contract_requested_at,
                        'contract_generated_at': deal.contract_generated_at,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if deal.contract_status == 'failed':
                return Response(
                    {
                        'detail': 'Не удалось сформировать договор.',
                        'contract_status': deal.contract_status,
                        'contract_status_display': deal.get_contract_status_display(),
                        'contract_error_message': deal.contract_error_message,
                        'contract_requested_at': deal.contract_requested_at,
                        'contract_generated_at': deal.contract_generated_at,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        if not deal.contract_file:
            raise Http404('Договор не удалось сформировать.')
        return FileResponse(
            deal.contract_file.open('rb'),
            as_attachment=True,
            filename=f'contract-{deal.deal_number}.pdf',
            content_type='application/pdf',
        )

    @action(detail=True, methods=['post'], url_path='regenerate_contract')
    def regenerate_contract(self, request, pk=None):
        """Перегенерировать PDF-договор."""
        if not request.user.is_employee:
            return Response(
                {'detail': 'Доступно только сотрудникам.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        deal = self.get_object()
        deal = deals_service.queue_contract_generation(
            deal,
            force=True,
            actor=request.user,
        )
        return Response(serializers.DealSerializer(deal).data)


class PropertyViewingViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyViewing.objects.select_related(
        'property', 'client_profile__user', 'employee_profile__user', 'payment'
    ).all()
    serializer_class = serializers.PropertyViewingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        property_id = self.request.query_params.get('property')
        if property_id:
            qs = qs.filter(property_id=property_id)
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(client_profile__user=user)
        elif user.is_authenticated and user.is_employee and not user.is_admin_or_manager:
            # Агент видит только свои просмотры, менеджер/админ — все.
            qs = qs.filter(employee_profile__user=user)
        return qs


class ViewingPaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        viewing_id = request.data.get('viewing_id')
        if not viewing_id:
            return Response(
                {'viewing_id': ['Поле viewing_id обязательно.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        viewing = get_object_or_404(
            models.PropertyViewing.objects.select_related('property', 'client_profile__user'),
            pk=viewing_id,
        )
        try:
            payment = create_viewing_payment(viewing, request.user, request)
        except ViewingPaymentAccessDenied as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except (ViewingPaymentValidationError, SberAcquiringError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            serializers.ViewingPaymentSerializer(payment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class ViewingPaymentSuccessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment_id = request.query_params.get('payment_id')
        payment = get_object_or_404(
            models.ViewingPayment.objects.select_related('viewing__client_profile__user'),
            pk=payment_id,
        )
        if (
            request.user.id != payment.client_id
            and not request.user.is_employee
            and not request.user.is_admin_or_manager
        ):
            return Response({'detail': 'Недостаточно прав.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            payment, response_payload = sync_payment_with_sber(payment, actor=request.user)
        except (ViewingPaymentValidationError, SberAcquiringError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        http_status = (
            status.HTTP_200_OK
            if payment.status == models.ViewingPayment.STATUS_PAID
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(
            {
                'payment': serializers.ViewingPaymentSerializer(payment, context={'request': request}).data,
                'sber_response': response_payload,
            },
            status=http_status,
        )


class ViewingPaymentFailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment_id = request.query_params.get('payment_id')
        payment = get_object_or_404(models.ViewingPayment, pk=payment_id)
        if (
            request.user.id != payment.client_id
            and not request.user.is_employee
            and not request.user.is_admin_or_manager
        ):
            return Response({'detail': 'Недостаточно прав.'}, status=status.HTTP_403_FORBIDDEN)
        payment = mark_payment_failed(
            payment,
            actor=request.user,
            comment='Клиент вернулся на fail-URL после неуспешной оплаты.',
        )
        return Response(
            serializers.ViewingPaymentSerializer(payment, context={'request': request}).data,
        )


class ViewingPaymentWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        order_id = request.data.get('orderId') or request.data.get('order_id')
        if not order_id:
            return Response({'detail': 'orderId is required.'}, status=status.HTTP_400_BAD_REQUEST)
        payment = get_object_or_404(models.ViewingPayment, sber_order_id=order_id)
        try:
            payment, _ = sync_payment_with_sber(payment)
        except (ViewingPaymentValidationError, SberAcquiringError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': payment.status})


class ViewingPaymentRefundView(APIView):
    permission_classes = [IsAdminOrManager]

    def post(self, request, payment_id: int):
        payment = get_object_or_404(models.ViewingPayment, pk=payment_id)
        amount = request.data.get('amount')
        try:
            refund_amount = None if amount in (None, '') else Decimal(str(amount))
            payment = refund_payment(
                payment,
                actor=request.user,
                amount=refund_amount,
            )
        except (ViewingPaymentValidationError, SberAcquiringError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializers.ViewingPaymentSerializer(payment, context={'request': request}).data)


class TaskViewSet(viewsets.ModelViewSet):
    """Задачи сотрудников агентства."""
    queryset = models.Task.objects.select_related(
        'status', 'assignee', 'created_by', 'client_profile__user', 'property',
        'request', 'deal',
    ).all()
    serializer_class = serializers.TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['due_date', 'created_at', 'priority']
    search_fields = ['title', 'description']

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.exclude(
            completed_at__isnull=False,
            status__code__in=business_rules.ACTIVE_TASK_STATUS_CODES,
        )
        user = self.request.user
        params = self.request.query_params
        if user.is_authenticated and user.is_client:
            qs = qs.filter(client_profile__user=user)
        elif user.is_authenticated and not user.is_admin_or_manager:
            qs = qs.filter(Q(assignee=user) | Q(created_by=user))
        if params.get('status'):
            qs = qs.filter(status_id=params['status'])
        if params.get('status_code'):
            codes = [c.strip() for c in params['status_code'].split(',')
                     if c.strip()]
            qs = qs.filter(status__code__in=codes)
        if params.get('assignee'):
            value = params['assignee']
            if value == 'me':
                qs = qs.filter(assignee=user)
            else:
                qs = qs.filter(assignee_id=value)
        if params.get('task_type'):
            qs = qs.filter(task_type=params['task_type'])
        if params.get('operation_type'):
            qs = qs.filter(
                _task_operation_filter_q(params['operation_type']),
            )
        if params.get('request'):
            qs = qs.filter(request_id=params['request'])
        qs = _apply_date_range_filter(
            qs,
            params,
            field_name='created_at',
            use_date_lookup=True,
        )
        if params.get('completed_after'):
            qs = qs.filter(completed_at__gte=params['completed_after'])
        if params.get('completed_before'):
            qs = qs.filter(completed_at__lte=params['completed_before'])
        return qs

    def get_permissions(self):
        if self.action in {'list', 'retrieve'}:
            return [IsAuthenticated()]
        return [IsEmployee()]

    def perform_create(self, serializer):
        assignee = serializer.validated_data.get('assignee')
        if assignee and not self.request.user.is_admin_or_manager:
            try:
                business_rules.assert_can_assign_task(assignee)
            except WorkloadLimitExceeded as exc:
                raise ValidationError({'assignee': [exc.detail]})

        # Статус обязателен в мод��ли, но фронт его не передаёт при создании —
        # подставляем начальный статус «new» автоматически.
        save_kwargs = {'created_by': self.request.user}
        if 'status' not in serializer.validated_data:
            initial_status = business_rules.status_by_code(models.TaskStatus, 'new')
            if initial_status is None:
                raise ValidationError(
                    {'detail': 'Справочник статусов задач не заполнен. Статус «new» не найден.'}
                )
            save_kwargs['status'] = initial_status

        task = serializer.save(**save_kwargs)
        audit_service.log_event(
            entity=task,
            action_code='created',
            action_label='Создание задачи',
            actor=self.request.user,
            message='Задача создана.',
            metadata={
                'task_type': task.task_type,
                'assignee_id': task.assignee_id,
            },
            property_obj=task.property,
            request_obj=task.request,
            deal_obj=task.deal,
        )
        enqueue_task_assigned(task=task)

    def perform_update(self, serializer):
        task = serializer.instance
        if task.is_terminal:
            raise ValidationError(
                {'detail': 'Нельзя редактировать завершённую задачу.'},
            )
        changed_fields = sorted(serializer.validated_data.keys())
        before_snapshot = audit_service.snapshot_fields(
            task,
            changed_fields,
        )
        assignee = serializer.validated_data.get('assignee', task.assignee)
        assignee_changed = assignee and assignee != task.assignee
        if assignee_changed and not self.request.user.is_admin_or_manager:
            try:
                business_rules.assert_can_assign_task(
                    assignee,
                    exclude_pk=task.pk if task.assignee_id == assignee.pk else None,
                )
            except WorkloadLimitExceeded as exc:
                raise ValidationError({'assignee': [exc.detail]})
        task = serializer.save()
        field_changes = audit_service.diff_field_snapshots(
            before_snapshot,
            audit_service.snapshot_fields(task, changed_fields),
        )
        audit_service.log_event(
            entity=task,
            action_code='updated',
            action_label='Редактирование задачи',
            actor=self.request.user,
            message='Карточка задачи обновлена.',
            metadata={
                'changed_fields': changed_fields,
                'field_changes': field_changes,
            },
            property_obj=task.property,
            request_obj=task.request,
            deal_obj=task.deal,
        )

    def perform_destroy(self, instance):
        if instance.is_terminal:
            raise ValidationError(
                {'detail': 'Нельзя удалить завершённую задачу.'},
            )
        audit_service.log_event(
            entity=instance,
            action_code='deleted',
            action_label='Удаление задачи',
            actor=self.request.user,
            message='Задача удалена.',
            property_obj=instance.property,
            request_obj=instance.request,
            deal_obj=instance.deal,
        )
        super().perform_destroy(instance)

    @action(
        detail=False,
        methods=['get'],
        url_path='export',
        permission_classes=[IsAdminOrManager],
    )
    def export(self, request):
        """Экспорт списка задач в CSV, JSON или XLSX."""
        export_format = (
            request.query_params.get('export_format')
            or request.query_params.get('format')
            or 'csv'
        )
        queryset = self.filter_queryset(self.get_queryset())
        return data_exchange.export_tasks(
            queryset,
            export_format,
            user=request.user,
            title=data_exchange._export_title(
                data_exchange.TASK_EXPORT_DEFINITION,
                request.user,
            ),
        )

    @action(detail=False, methods=['post'], url_path='bulk-action')
    def bulk_action(self, request):
        serializer = serializers.TaskBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_ids = serializer.validated_data['ids']
        action_code = serializer.validated_data['action']
        result_text = serializer.validated_data.get('result')

        tasks = list(
            self.get_queryset()
            .filter(pk__in=requested_ids)
            .select_related('status', 'assignee', 'created_by')
        )
        found_ids = {task.pk for task in tasks}
        processed = 0
        errors = []

        for task in tasks:
            try:
                if action_code == 'pause':
                    if (
                        not request.user.is_admin_or_manager
                        and task.assignee_id != request.user.id
                    ):
                        raise ValidationError(
                            {'detail': 'Нельзя приостанавливать чужую задачу.'},
                        )
                    _pause_task_instance(task, actor=request.user)
                    audit_service.log_event(
                        entity=task,
                        action_code='bulk_paused',
                        action_label='Массовая пауза задачи',
                        actor=request.user,
                        message='Задача приостановлена через массовую операцию.',
                        metadata={'bulk': True, 'action': 'pause'},
                        property_obj=task.property,
                        request_obj=task.request,
                        deal_obj=task.deal,
                    )
                elif action_code == 'complete':
                    if (
                        not request.user.is_admin_or_manager
                        and task.assignee_id != request.user.id
                    ):
                        raise ValidationError(
                            {'detail': 'Нельзя завершить чужую задачу.'},
                        )
                    from . import task_actions
                    task_actions.complete_task(
                        task,
                        actor=request.user,
                        result=result_text,
                    )
                    audit_service.log_event(
                        entity=task,
                        action_code='bulk_completed',
                        action_label='Массовое завершение задачи',
                        actor=request.user,
                        message='Задача завершена через массовую операцию.',
                        metadata={'bulk': True, 'action': 'complete'},
                        property_obj=task.property,
                        request_obj=task.request,
                        deal_obj=task.deal,
                    )
                elif action_code == 'delete':
                    with transaction.atomic():
                        audit_service.log_event(
                            entity=task,
                            action_code='bulk_deleted',
                            action_label='Массовое удаление задачи',
                            actor=request.user,
                            message='Задача удалена через массовую операцию.',
                            metadata={'bulk': True, 'action': 'delete'},
                            property_obj=task.property,
                            request_obj=task.request,
                            deal_obj=task.deal,
                        )
                        super().perform_destroy(task)
                else:
                    raise ValidationError({'detail': 'Неизвестное действие.'})
            except ValidationError as exc:
                payload = _validation_error_payload(exc)
                errors.append({
                    'id': task.pk,
                    'detail': payload.get('detail', 'Не удалось обработать задачу.'),
                })
                continue
            processed += 1

        not_found_ids = [
            task_id for task_id in requested_ids
            if task_id not in found_ids
        ]
        return Response({
            'requested': len(requested_ids),
            'processed': processed,
            'action': action_code,
            'errors': errors,
            'not_found_ids': not_found_ids,
        })

    @action(detail=True, methods=['post'], url_path='change_status')
    def change_status(self, request, pk=None):
        """Смена статуса задачи."""
        task = self.get_object()
        if (task.assignee_id != request.user.id
                and not request.user.is_admin_or_manager):
            return Response(
                {'detail': 'Нельзя менять статус чужой задачи.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        status_id = request.data.get('status_id')
        if not status_id:
            return Response({'detail': 'Не указан статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        new_status = models.TaskStatus.objects.filter(pk=status_id).first()
        if not new_status:
            return Response({'detail': 'Неизвестный статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if (new_status.code == 'in_progress'
                and task.assignee_id
                and not request.user.is_admin_or_manager):
            try:
                business_rules.assert_can_start_task(task.assignee, task)
            except WorkloadLimitExceeded as exc:
                return Response(
                    {'detail': exc.detail, 'code': exc.code},
                    status=status.HTTP_409_CONFLICT,
                )
        if new_status.code == 'done':
            from . import task_actions
            task, _ = task_actions.complete_task(
                task,
                actor=request.user,
                result=request.data.get('result'),
            )
            return Response(serializers.TaskSerializer(task).data)

        old_status_code = task.status.code if task.status_id else None
        old_status = task.status
        task.status = new_status
        update_fields = ['status', 'updated_at']
        if new_status.code == 'cancelled':
            task.completed_at = timezone.now()
            task.is_auto_closed = False
            update_fields.extend(['completed_at', 'is_auto_closed'])
        elif old_status_code in models.Task.TERMINAL_STATUS_CODES:
            if task.completed_at is not None:
                task.completed_at = None
                update_fields.append('completed_at')
            if task.is_auto_closed:
                task.is_auto_closed = False
                update_fields.append('is_auto_closed')
        task.save(update_fields=list(dict.fromkeys(update_fields)))
        audit_service.log_event(
            entity=task,
            action_code='status_changed',
            action_label='Смена статуса задачи',
            actor=request.user,
            message=(
                f'Статус задачи изменён с «{old_status.name}» '
                f'на «{new_status.name}».'
            ),
            metadata={
                'from_status_id': old_status.pk,
                'from_status_code': old_status_code,
                'to_status_id': new_status.pk,
                'to_status_code': new_status.code,
            },
            property_obj=task.property,
            request_obj=task.request,
            deal_obj=task.deal,
        )
        return Response(serializers.TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Перевести задачу в работу."""
        task = self.get_object()
        if task.assignee_id != request.user.id \
                and not request.user.is_admin_or_manager:
            return Response(
                {'detail': 'Нельзя стартовать чужую задачу.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        in_progress = business_rules.status_by_code(
            models.TaskStatus, 'in_progress',
        )
        if not in_progress:
            return Response(
                {'detail': 'Справочник статусов не заполнен.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            business_rules.assert_can_start_task(task.assignee, task)
        except WorkloadLimitExceeded as exc:
            return Response(
                {'detail': exc.detail, 'code': exc.code},
                status=status.HTTP_409_CONFLICT,
            )
        old_status_code = task.status.code if task.status_id else None
        old_status = task.status
        task.status = in_progress
        update_fields = ['status', 'updated_at']
        if old_status_code in models.Task.TERMINAL_STATUS_CODES:
            if task.completed_at is not None:
                task.completed_at = None
                update_fields.append('completed_at')
            if task.is_auto_closed:
                task.is_auto_closed = False
                update_fields.append('is_auto_closed')
        task.save(update_fields=list(dict.fromkeys(update_fields)))
        audit_service.log_event(
            entity=task,
            action_code='started',
            action_label='Перевод в работу',
            actor=request.user,
            message=(
                f'Задача переведена из статуса «{old_status.name}» '
                f'в «{in_progress.name}».'
            ),
            metadata={
                'from_status_code': old_status_code,
                'to_status_code': in_progress.code,
            },
            property_obj=task.property,
            request_obj=task.request,
            deal_obj=task.deal,
        )
        return Response(serializers.TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Перевести задачу в ожидание."""
        task = self.get_object()
        if task.assignee_id != request.user.id \
                and not request.user.is_admin_or_manager:
            return Response(
                {'detail': 'Нельзя приостанавливать чужую задачу.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        waiting = business_rules.status_by_code(
            models.TaskStatus, 'waiting',
        )
        if not waiting:
            return Response(
                {'detail': 'Справочник статусов не заполнен.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        old_status_code = task.status.code if task.status_id else None
        old_status = task.status
        task.status = waiting
        update_fields = ['status', 'updated_at']
        if old_status_code in models.Task.TERMINAL_STATUS_CODES:
            if task.completed_at is not None:
                task.completed_at = None
                update_fields.append('completed_at')
            if task.is_auto_closed:
                task.is_auto_closed = False
                update_fields.append('is_auto_closed')
        task.save(update_fields=list(dict.fromkeys(update_fields)))
        audit_service.log_event(
            entity=task,
            action_code='paused',
            action_label='Пауза задачи',
            actor=request.user,
            message=(
                f'Задача переведена из статуса «{old_status.name}» '
                f'в «{waiting.name}».'
            ),
            metadata={
                'from_status_code': old_status_code,
                'to_status_code': waiting.code,
            },
            property_obj=task.property,
            request_obj=task.request,
            deal_obj=task.deal,
        )
        return Response(serializers.TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Завершить задачу."""
        task = self.get_object()
        if (task.assignee_id != request.user.id
                and not request.user.is_admin_or_manager):
            return Response(
                {'detail': 'Нельзя завершить чужую задачу.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        from . import task_actions
        task, changed = task_actions.complete_task(
            task,
            actor=request.user,
            result=request.data.get('result'),
        )
        if not changed:
            return Response(serializers.TaskSerializer(task).data)
        return Response(serializers.TaskSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='record_step')
    def record_step(self, request, pk=None):
        """Зафиксировать шаг TaskWorkflow."""
        task = self.get_object()
        if (task.assignee_id != request.user.id
                and not request.user.is_admin_or_manager):
            return Response(
                {'detail': 'Нельзя дописывать шаги чужой задачи.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        step = (request.data.get('step') or '').strip()
        if not step:
            return Response(
                {'detail': 'Поле step обязательно.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from . import task_actions
        task = task_actions.record_step(
            task,
            step=step,
            outcome=request.data.get('outcome'),
            note=request.data.get('note'),
            actor=request.user,
        )
        return Response(serializers.TaskSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='schedule_viewing')
    def schedule_viewing(self, request, pk=None):
        task = self.get_object()
        if (task.assignee_id != request.user.id and not request.user.is_admin_or_manager):
            return Response(
                {'detail': 'Нельзя назначать просмотр по чужой задаче.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        viewing_date = request.data.get('viewing_date')
        if not viewing_date:
            return Response(
                {'detail': 'Поле viewing_date обязательно.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            parsed_date = drf_serializers.DateTimeField().to_internal_value(viewing_date)
            from . import task_actions
            task, viewing = task_actions.schedule_task_showing(
                task,
                actor=request.user,
                viewing_date=parsed_date,
                note=request.data.get('note'),
            )
        except ValidationError as exc:
            return Response(_validation_error_payload(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'task': serializers.TaskSerializer(task, context={'request': request}).data,
            'viewing': serializers.PropertyViewingSerializer(viewing, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'], url_path='initiate_viewing_payment')
    def initiate_viewing_payment(self, request, pk=None):
        task = self.get_object()
        if (task.assignee_id != request.user.id and not request.user.is_admin_or_manager):
            return Response(
                {'detail': 'Нельзя создавать оплату по чужой задаче.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        from . import task_actions
        try:
            task, payment = task_actions.initiate_showing_payment_for_task(
                task,
                actor=request.user,
                request=request,
            )
        except (ValidationError, ViewingPaymentValidationError, SberAcquiringError) as exc:
            payload = _validation_error_payload(exc) if isinstance(exc, ValidationError) else {'detail': str(exc)}
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'task': serializers.TaskSerializer(task, context={'request': request}).data,
            'payment': serializers.ViewingPaymentSerializer(payment, context={'request': request}).data,
        })

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Текущая задача в работе."""
        if not request.user.is_employee:
            return Response(None)
        task = models.Task.objects.select_related(
            'status', 'request', 'client', 'property',
        ).filter(
            assignee=request.user,
            status__code='in_progress',
            completed_at__isnull=True,
        ).order_by('-updated_at').first()
        if task is None:
            return Response(None)
        return Response(serializers.TaskSerializer(task).data)


class OutgoingEmailViewSet(viewsets.ModelViewSet):
    """Очередь исходящих писем."""
    queryset = models.OutgoingEmail.objects.select_related(
        'recipient', 'sender', 'task', 'request', 'property',
    ).all()
    serializer_class = serializers.OutgoingEmailSerializer
    permission_classes = [IsEmployee]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'sent_at']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('request'):
            qs = qs.filter(request_id=params['request'])
        return qs

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Повторная попытка отправки неудавшегося письма."""
        email = self.get_object()
        if email.status != 'failed':
            return Response(
                {'detail': 'Можно повторить только неудавшиеся письма.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        resend_email(email)
        email.refresh_from_db()
        return Response(serializers.OutgoingEmailSerializer(email).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Единый журнал значимых действий системы."""
    queryset = models.AuditLog.objects.select_related(
        'actor', 'entity_type', 'action',
    ).all()
    serializer_class = serializers.AuditLogSerializer
    # Клиентам аудит-лог не показываем: даже фильтрация "только своё"
    # всё равно раскрывает структуру и метаданные внутренних процессов.
    permission_classes = [IsEmployee]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        user = self.request.user

        if user.is_authenticated and user.is_employee and not user.is_admin_or_manager:
            qs = qs.filter(
                Q(property__isnull=False)
                | Q(request__agent=user)
                | Q(deal__agent=user)
                | Q(task__assignee=user)
                | Q(task__created_by=user)
            ).distinct()

        if params.get('property'):
            qs = qs.filter(property_id=params['property'])
        if params.get('request'):
            qs = qs.filter(request_id=params['request'])
        if params.get('task'):
            qs = qs.filter(task_id=params['task'])
        if params.get('deal'):
            qs = qs.filter(deal_id=params['deal'])
        if params.get('entity_type'):
            entity_type = str(params['entity_type']).strip()
            if entity_type.isdigit():
                qs = qs.filter(entity_type_id=entity_type)
            else:
                qs = qs.filter(entity_type__code=entity_type)
        if params.get('entity_id'):
            qs = qs.filter(entity_id=params['entity_id'])
        if params.get('action_id'):
            qs = qs.filter(action_id=params['action_id'])
        if params.get('action_code'):
            qs = qs.filter(action__code=params['action_code'])
        return qs

    @action(
        detail=False,
        methods=['get'],
        url_path='export',
        permission_classes=[IsAdminOrManager],
    )
    def export(self, request):
        """Экспорт журнала аудита в CSV, JSON или XLSX."""
        export_format = (
            request.query_params.get('export_format')
            or request.query_params.get('format')
            or 'csv'
        )
        queryset = self.filter_queryset(self.get_queryset())
        return data_exchange.export_audit(
            queryset,
            export_format,
            user=request.user,
        )


class DashboardStatsView(APIView):
    """Агрегированные показатели учётной системы."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            'properties_total': models.Property.objects.count(),
            'properties_active': models.Property.objects.filter(
                status__code='active').count(),
            'requests_open': models.Request.objects.filter(
                status__code__in=business_rules.ACTIVE_REQUEST_STATUS_CODES,
            ).count(),
            'requests_total': models.Request.objects.count(),
            'deals_total': models.Deal.objects.count(),
            'deals_sum': models.Deal.objects.aggregate(
                total=Sum('price_final'))['total'] or 0,
            'clients_total': User.objects.filter(user_type='client').count(),
            'employees_total': User.objects.filter(user_type='employee').count(),
            'by_operation': list(
                models.Property.objects
                .values('operation_type__name')
                .annotate(total=Count('id'))
            ),
        }
        if user.is_authenticated and user.is_employee:
            open_tasks = models.Task.objects.filter(
                status__code__in=business_rules.ACTIVE_TASK_STATUS_CODES,
                completed_at__isnull=True,
            )
            if not user.is_admin_or_manager:
                open_tasks = open_tasks.filter(assignee=user)
            data['tasks_open'] = open_tasks.count()
        return Response(data)


class PropertyExportView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        queryset = models.Property.objects.select_related(
            'operation_type', 'status', 'property_type_ref',
            'house__street__city', 'house__building_details',
            'details', 'commercial_details',
        ).prefetch_related(
            'photos',
            'owners__client_profile__user',
            'amenities__amenity',
        ).all()
        queryset = _apply_property_filters(queryset, request.query_params)
        export_format = request.query_params.get('export_format', 'csv')
        return data_exchange.export_properties(
            queryset,
            export_format,
            user=request.user,
            title=data_exchange._export_title(
                data_exchange.PROPERTY_EXPORT_DEFINITION,
                request.user,
            ),
        )


class DealsReportView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        payload = reports.build_deals_report(
            request.query_params,
            user=request.user,
        )
        export_format = request.query_params.get('export')
        if export_format:
            return reports.export_report(
                payload['definition'],
                payload['summary'],
                payload['rows'],
                export_format,
                ordering=payload.get('ordering'),
                title=payload.get('title'),
                user=request.user,
            )
        return Response({
            'report_code': payload['definition'].code,
            'title': payload['title'],
            'columns': [
                {'key': key, 'label': label}
                for key, label in payload['definition'].columns
            ],
            'ordering': payload.get('ordering'),
            'ordering_options': [
                {'value': value, 'label': label}
                for value, label in payload['definition'].ordering_options
            ],
            'summary': payload['summary'],
            'rows': payload['rows'],
        })


class DictionaryExportView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        export_format = request.query_params.get('export_format', 'json')
        return data_exchange.export_dictionaries(export_format, user=request.user)


class TasksReportView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        payload = reports.build_tasks_report(
            request.query_params,
            user=request.user,
        )
        export_format = request.query_params.get('export')
        if export_format:
            return reports.export_report(
                payload['definition'],
                payload['summary'],
                payload['rows'],
                export_format,
                ordering=payload.get('ordering'),
                title=payload.get('title'),
                user=request.user,
            )
        return Response({
            'report_code': payload['definition'].code,
            'title': payload['title'],
            'columns': [
                {'key': key, 'label': label}
                for key, label in payload['definition'].columns
            ],
            'ordering': payload.get('ordering'),
            'ordering_options': [
                {'value': value, 'label': label}
                for value, label in payload['definition'].ordering_options
            ],
            'summary': payload['summary'],
            'rows': payload['rows'],
        })


class ViewingPaymentsReportView(APIView):
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        payload = reports.build_viewing_payments_report(
            request.query_params,
            user=request.user,
        )
        export_format = request.query_params.get('export')
        if export_format:
            return reports.export_report(
                payload['definition'],
                payload['summary'],
                payload['rows'],
                export_format,
                ordering=payload.get('ordering'),
                title=payload.get('title'),
                user=request.user,
            )
        return Response({
            'report_code': payload['definition'].code,
            'title': payload['title'],
            'columns': [
                {'key': key, 'label': label}
                for key, label in payload['definition'].columns
            ],
            'ordering': payload.get('ordering'),
            'ordering_options': [
                {'value': value, 'label': label}
                for value, label in payload['definition'].ordering_options
            ],
            'summary': payload['summary'],
            'rows': payload['rows'],
        })
