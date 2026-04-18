"""
REST-представления приложения `key`.

Архитектура: ViewSet-ы для CRUD + отдельные APIView для аутентификации
и интеграции с ФИАС.
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import models, serializers
from .fias import FIASClient

User = get_user_model()


# ====== Аутентификация =====================================================

class RegisterView(APIView):
    """Регистрация нового пользователя (сотрудника или клиента)."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = serializers.RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializers.UserSerializer(user).data,
                        status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """Получение JWT пары access/refresh."""
    permission_classes = [AllowAny]


class MeView(APIView):
    """Информация о текущем пользователе."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serializers.UserSerializer(request.user).data)


# ====== Справочники (только чтение, публичные) ============================

class OperationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.OperationType.objects.all()
    serializer_class = serializers.OperationTypeSerializer
    permission_classes = [AllowAny]


class PropertyStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.PropertyStatus.objects.all()
    serializer_class = serializers.PropertyStatusSerializer
    permission_classes = [AllowAny]


class RequestStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.RequestStatus.objects.all()
    serializer_class = serializers.RequestStatusSerializer
    permission_classes = [AllowAny]


class UserRoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.UserRole.objects.all()
    serializer_class = serializers.UserRoleSerializer


# ====== Адресная иерархия =================================================

class CityViewSet(viewsets.ModelViewSet):
    queryset = models.City.objects.all()
    serializer_class = serializers.CitySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'region']


class StreetViewSet(viewsets.ModelViewSet):
    queryset = models.Street.objects.select_related('city').all()
    serializer_class = serializers.StreetSerializer
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

    def get_queryset(self):
        qs = super().get_queryset()
        street_id = self.request.query_params.get('street')
        if street_id:
            qs = qs.filter(street_id=street_id)
        return qs


class AddressViewSet(viewsets.ModelViewSet):
    queryset = models.Address.objects.select_related(
        'house__street__city').all()
    serializer_class = serializers.AddressSerializer


# ====== ФИАС-прокси =======================================================

class FIASSearchView(APIView):
    """
    Прокси-эндпоинт для поиска адресов через ФИАС-сервис ФНС.

    Токен ФИАС хранится на сервере и передаётся в заголовке ``master-token``.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query or len(query) < 3:
            return Response({'results': []})
        try:
            client = FIASClient()
            results = client.search_address(query, limit=15)
        except Exception as exc:  # pragma: no cover
            return Response({'error': str(exc)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'results': results})


# ====== Пользователи и профили ============================================

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('role').all()
    serializer_class = serializers.UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'phone']

    def get_queryset(self):
        qs = super().get_queryset()
        user_type = self.request.query_params.get('user_type')
        if user_type:
            qs = qs.filter(user_type=user_type)
        return qs


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    queryset = models.EmployeeProfile.objects.select_related('user').all()
    serializer_class = serializers.EmployeeProfileSerializer


class ClientProfileViewSet(viewsets.ModelViewSet):
    queryset = models.ClientProfile.objects.select_related('user').all()
    serializer_class = serializers.ClientProfileSerializer


# ====== Объекты недвижимости ==============================================

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = models.Property.objects.select_related(
        'operation_type', 'status', 'address__house__street__city'
    ).prefetch_related('photos', 'feature_values__feature').all()
    serializer_class = serializers.PropertySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['price', 'created_at', 'area_total']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        operation = params.get('operation_type')
        if operation:
            qs = qs.filter(operation_type_id=operation)

        status_id = params.get('status')
        if status_id:
            qs = qs.filter(status_id=status_id)

        rooms = params.get('rooms')
        if rooms:
            qs = qs.filter(rooms_count=rooms)

        if params.get('min_price'):
            qs = qs.filter(price__gte=params['min_price'])
        if params.get('max_price'):
            qs = qs.filter(price__lte=params['max_price'])

        return qs

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Смена статуса объекта с записью в историю."""
        property_obj = self.get_object()
        new_status_id = request.data.get('status_id')
        if not new_status_id:
            return Response({'detail': 'status_id обязателен'},
                            status=status.HTTP_400_BAD_REQUEST)
        property_obj.status_id = new_status_id
        property_obj.save()
        models.PropertyStatusHistory.objects.create(
            property=property_obj,
            status_id=new_status_id,
            changed_by=request.user,
        )
        return Response(serializers.PropertySerializer(property_obj).data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """История смен статусов объекта."""
        property_obj = self.get_object()
        qs = property_obj.status_history.all()
        return Response(
            serializers.PropertyStatusHistorySerializer(qs, many=True).data
        )


class PropertyFeatureViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyFeature.objects.all()
    serializer_class = serializers.PropertyFeatureSerializer


class PropertyPhotoViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyPhoto.objects.all()
    serializer_class = serializers.PropertyPhotoSerializer


class PropertyDocumentViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyDocument.objects.select_related('verified_by').all()
    serializer_class = serializers.PropertyDocumentSerializer

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Отметить документ как проверенный."""
        doc = self.get_object()
        doc.is_verified = True
        doc.verified_by = request.user
        doc.verified_at = timezone.now()
        doc.save()
        return Response(serializers.PropertyDocumentSerializer(doc).data)


# ====== Заявки, сделки, просмотры =========================================

class RequestViewSet(viewsets.ModelViewSet):
    queryset = models.Request.objects.select_related(
        'client', 'agent', 'operation_type', 'status'
    ).all()
    serializer_class = serializers.RequestSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        qs = super().get_queryset()
        status_id = self.request.query_params.get('status')
        if status_id:
            qs = qs.filter(status_id=status_id)
        return qs

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        req = self.get_object()
        closed = models.RequestStatus.objects.filter(code='closed').first()
        if closed:
            req.status = closed
        req.closed_at = timezone.now()
        req.save()
        return Response(serializers.RequestSerializer(req).data)


class DealViewSet(viewsets.ModelViewSet):
    queryset = models.Deal.objects.select_related(
        'property', 'agent', 'client', 'operation_type'
    ).all()
    serializer_class = serializers.DealSerializer


class PropertyViewingViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyViewing.objects.select_related(
        'property', 'client', 'agent'
    ).all()
    serializer_class = serializers.PropertyViewingSerializer


# ====== Статистика для дашборда ==========================================

class DashboardStatsView(APIView):
    """Сводная статистика для главного экрана."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            'properties_total': models.Property.objects.count(),
            'properties_active': models.Property.objects.filter(
                status__code='active').count(),
            'requests_open': models.Request.objects.filter(
                status__code='open').count(),
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
        return Response(data)
