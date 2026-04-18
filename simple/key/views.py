"""
REST-представления приложения ``key``.

Архитектура: ViewSet-ы для CRUD + отдельные APIView для аутентификации
и интеграции с DaData (подсказки адресов).
"""
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q
from django.utils import timezone
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import models, serializers
from .dadata import DadataClient
from .permissions import (
    IsAdminOrManager,
    IsEmployee,
    IsEmployeeOrReadOnly,
    IsAdminOrManagerOrReadOnly,
)

User = get_user_model()


# ====== Аутентификация =====================================================

class RegisterView(APIView):
    """
    Регистрация нового пользователя.

    Принимаются только ``username``, ``email``, ``phone`` и ``password``.
    Тип пользователя всегда ``client``, должность не назначается —
    это делает администратор или менеджер агентства через отдельный
    эндпоинт ``/users/{id}/assign_role/``.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = serializers.RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializers.UserSerializer(user).data,
                        status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """Получение пары токенов ``access`` / ``refresh``."""
    permission_classes = [AllowAny]


class MeView(APIView):
    """Информация о текущем пользователе."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serializers.UserSerializer(request.user).data)


# ====== Справочники =========================================================

class OperationTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.OperationType.objects.all()
    serializer_class = serializers.OperationTypeSerializer
    permission_classes = [IsAuthenticated]


class PropertyStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.PropertyStatus.objects.all()
    serializer_class = serializers.PropertyStatusSerializer
    permission_classes = [IsAuthenticated]


class RequestStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.RequestStatus.objects.all()
    serializer_class = serializers.RequestStatusSerializer
    permission_classes = [IsAuthenticated]


class DealStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.DealStatus.objects.all()
    serializer_class = serializers.DealStatusSerializer
    permission_classes = [IsAuthenticated]


class TaskStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.TaskStatus.objects.all()
    serializer_class = serializers.TaskStatusSerializer
    permission_classes = [IsAuthenticated]


class UserRoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.UserRole.objects.all()
    serializer_class = serializers.UserRoleSerializer
    permission_classes = [IsAuthenticated]


# ====== Адресная иерархия ==================================================

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
    queryset = models.Address.objects.select_related(
        'house__street__city').all()
    serializer_class = serializers.AddressSerializer
    permission_classes = [IsEmployeeOrReadOnly]


# ====== Подсказки адресов (прокси к DaData) ================================

class DadataSuggestAddressView(APIView):
    """
    Прокси-эндпоинт подсказок адресов DaData.

    Ключ к DaData хранится только в настройках сервера и никогда не
    передаётся в браузер. Принимает ``GET ?q=...`` и возвращает массив
    нормализованных подсказок.
    """
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


# ====== Пользователи и профили ============================================

class UserViewSet(viewsets.ModelViewSet):
    """
    Управление пользователями.

    Просмотр списка доступен сотрудникам. Назначение роли/типа —
    только администратору и менеджеру.
    """
    queryset = User.objects.select_related('role').all()
    serializer_class = serializers.UserSerializer
    permission_classes = [IsEmployee]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'phone']

    def get_queryset(self):
        qs = super().get_queryset()
        user_type = self.request.query_params.get('user_type')
        if user_type:
            qs = qs.filter(user_type=user_type)
        role_code = self.request.query_params.get('role')
        if role_code:
            qs = qs.filter(role__code=role_code)
        return qs

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update',
                           'destroy', 'assign_role'}:
            return [IsAdminOrManager()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], url_path='assign_role')
    def assign_role(self, request, pk=None):
        """
        Назначить пользователю тип учётной записи и должность.

        Доступно только администратору или менеджеру. Принимает
        поля ``user_type``, ``role_id`` и/или ``is_active``.
        """
        target = self.get_object()
        serializer = serializers.UserRoleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'user_type' in data:
            target.user_type = data['user_type']
        if 'role' in data:
            target.role = data['role']
        if 'is_active' in data:
            target.is_active = data['is_active']
        target.save()
        return Response(serializers.UserSerializer(target).data)


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    queryset = models.EmployeeProfile.objects.select_related('user').all()
    serializer_class = serializers.EmployeeProfileSerializer
    permission_classes = [IsEmployee]


class ClientProfileViewSet(viewsets.ModelViewSet):
    queryset = models.ClientProfile.objects.select_related('user').all()
    serializer_class = serializers.ClientProfileSerializer
    permission_classes = [IsEmployeeOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(user=user)
        return qs


# ====== Объекты недвижимости ==============================================

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = models.Property.objects.select_related(
        'operation_type', 'status', 'address__house__street__city'
    ).prefetch_related('photos', 'feature_values__feature').all()
    serializer_class = serializers.PropertySerializer
    permission_classes = [IsEmployeeOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['price', 'created_at', 'area_total']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        if params.get('operation_type'):
            qs = qs.filter(operation_type_id=params['operation_type'])
        if params.get('status'):
            qs = qs.filter(status_id=params['status'])
        if params.get('rooms'):
            qs = qs.filter(rooms_count=params['rooms'])
        if params.get('min_price'):
            qs = qs.filter(price__gte=params['min_price'])
        if params.get('max_price'):
            qs = qs.filter(price__lte=params['max_price'])

        return qs

    @action(detail=True, methods=['post'], url_path='change_status')
    def change_status(self, request, pk=None):
        """Смена статуса объекта с записью в историю."""
        property_obj = self.get_object()
        new_status_id = request.data.get('status_id')
        if not new_status_id:
            return Response({'detail': 'Не указан статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        property_obj.status_id = new_status_id
        property_obj.save()
        models.PropertyStatusHistory.objects.create(
            property=property_obj,
            status_id=new_status_id,
            changed_by=request.user,
        )
        return Response(serializers.PropertySerializer(
            property_obj, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """История смен статусов объекта."""
        property_obj = self.get_object()
        qs = property_obj.status_history.select_related('status', 'changed_by')
        return Response(
            serializers.PropertyStatusHistorySerializer(qs, many=True).data
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='upload_photo',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        permission_classes=[IsEmployee],
    )
    def upload_photo(self, request, pk=None):
        """
        Загрузить фото объекта.

        Принимает либо файл в поле ``image`` (multipart/form-data),
        либо внешний URL в поле ``url`` (application/json).
        """
        property_obj = self.get_object()
        image = request.FILES.get('image')
        url = request.data.get('url')
        if not image and not url:
            return Response(
                {'detail': 'Нужно передать файл image или ссылку url.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        photo = models.PropertyPhoto.objects.create(
            property=property_obj,
            image=image if image else None,
            url=url if not image else '',
            order=property_obj.photos.count(),
        )
        return Response(
            serializers.PropertyPhotoSerializer(
                photo, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class PropertyFeatureViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyFeature.objects.all()
    serializer_class = serializers.PropertyFeatureSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class PropertyPhotoViewSet(viewsets.ModelViewSet):
    """
    Фото объекта. Поддерживает два формата загрузки:
      * multipart/form-data с полем ``image`` — файл;
      * application/json с полем ``url`` — внешняя ссылка.
    """
    queryset = models.PropertyPhoto.objects.all()
    serializer_class = serializers.PropertyPhotoSerializer
    permission_classes = [IsEmployee]
    parser_classes = [MultiPartParser, FormParser, JSONParser]


class PropertyDocumentViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyDocument.objects.select_related('verified_by').all()
    serializer_class = serializers.PropertyDocumentSerializer
    permission_classes = [IsEmployee]

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Отметить документ как проверенный."""
        doc = self.get_object()
        doc.is_verified = True
        doc.verified_by = request.user
        doc.verified_at = timezone.now()
        doc.save()
        return Response(serializers.PropertyDocumentSerializer(doc).data)


# ====== Заявки, сделки, просмотры, задачи =================================

class RequestViewSet(viewsets.ModelViewSet):
    """
    Заявки клиентов.

    Правила доступа:
      * клиент видит и создаёт только свои заявки; закрыть может только
        свою и только в неоконечном статусе;
      * сотрудник видит все заявки. Может взять в работу неназначенную
        заявку (``POST /requests/{id}/take/``), прикрепить объект
        (``POST /requests/{id}/attach_property/``) и закрыть любую.
    """
    queryset = models.Request.objects.select_related(
        'client', 'agent', 'operation_type', 'status', 'property',
    ).prefetch_related('matches__property', 'matches__agent').all()
    serializer_class = serializers.RequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(client=user)

        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status_id=params['status'])
        if params.get('status_code'):
            qs = qs.filter(status__code=params['status_code'])
        # «scope=unassigned» — заявки без агента (для вкладки сотрудника).
        scope = params.get('scope')
        if scope == 'unassigned' and user.is_employee:
            qs = qs.filter(agent__isnull=True)
        elif scope == 'mine' and user.is_employee:
            qs = qs.filter(agent=user)
        return qs

    def perform_create(self, serializer):
        """
        Автозаполнение при подаче заявки клиентом.

        Клиент не имеет права указывать ``client`` (подставляем его из
        запроса) и не может назначить себе агента.
        """
        user = self.request.user
        extra = {}
        if user.is_authenticated and user.is_client:
            extra['client'] = user
            extra['agent'] = None
        elif not serializer.validated_data.get('client'):
            raise ValidationError(
                {'client': 'Укажите клиента заявки.'}
            )
        serializer.save(**extra)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """
        Закрыть заявку.

        Клиент может закрыть только свою заявку (отсечение происходит
        в ``get_queryset``). Повторное закрытие не допускается.
        """
        req = self.get_object()
        if req.status and req.status.code in {'closed', 'cancelled'}:
            return Response(
                {'detail': 'Заявка уже закрыта.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        closed = models.RequestStatus.objects.filter(code='closed').first()
        if closed:
            req.status = closed
        req.closed_at = timezone.now()
        req.save()
        return Response(serializers.RequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def take(self, request, pk=None):
        """
        Сотрудник берёт заявку в работу.

        Назначает себя агентом и переводит статус в «в обработке».
        Сигнал ``request_taken_create_task`` автоматически создаёт
        задачу «Связаться с клиентом».
        """
        if not request.user.is_employee:
            return Response(
                {'detail': 'Доступно только сотрудникам.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        req = self.get_object()
        if req.agent_id and req.agent_id != request.user.id:
            return Response(
                {'detail': 'Заявка уже взята другим сотрудником.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        req.agent = request.user
        processing = models.RequestStatus.objects.filter(
            code='processing').first()
        if processing:
            req.status = processing
        req.save()
        return Response(serializers.RequestSerializer(req).data)

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
            match.is_rejected = False
            match.is_offered = True
            if request.data.get('agent_note') is not None:
                match.agent_note = request.data['agent_note']
            match.save()
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
        deleted, _ = req.matches.filter(pk=match_id).delete()
        if not deleted:
            return Response({'detail': 'Вариант не найден.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RequestPropertyMatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Только чтение подборки; модификация — через действия RequestViewSet."""
    queryset = models.RequestPropertyMatch.objects.select_related(
        'property', 'agent', 'request'
    ).all()
    serializer_class = serializers.RequestPropertyMatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(request__client=user)
        request_id = self.request.query_params.get('request')
        if request_id:
            qs = qs.filter(request_id=request_id)
        return qs


class DealViewSet(viewsets.ModelViewSet):
    queryset = models.Deal.objects.select_related(
        'property', 'agent', 'client', 'operation_type', 'status'
    ).all()
    serializer_class = serializers.DealSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(client=user)
        return qs

    @action(detail=True, methods=['post'], url_path='change_status')
    def change_status(self, request, pk=None):
        """Смена статуса сделки (воронка продаж)."""
        deal = self.get_object()
        status_id = request.data.get('status_id')
        if not status_id:
            return Response({'detail': 'Не указан статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        deal.status_id = status_id
        deal.save()
        return Response(serializers.DealSerializer(deal).data)


class PropertyViewingViewSet(viewsets.ModelViewSet):
    queryset = models.PropertyViewing.objects.select_related(
        'property', 'client', 'agent'
    ).all()
    serializer_class = serializers.PropertyViewingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_client:
            qs = qs.filter(client=user)
        return qs


class TaskViewSet(viewsets.ModelViewSet):
    """
    Задачи сотрудников агентства.

    Сотрудник видит свои задачи и задачи, где он исполнитель.
    Администратор/менеджер — все. Клиенты доступа не имеют.
    """
    queryset = models.Task.objects.select_related(
        'status', 'assignee', 'created_by', 'client', 'property',
        'request', 'deal',
    ).all()
    serializer_class = serializers.TaskSerializer
    permission_classes = [IsEmployee]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['due_date', 'created_at', 'priority']
    search_fields = ['title', 'description']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_admin_or_manager:
            qs = qs.filter(Q(assignee=user) | Q(created_by=user))
        if self.request.query_params.get('status'):
            qs = qs.filter(status_id=self.request.query_params['status'])
        if self.request.query_params.get('assignee'):
            qs = qs.filter(assignee_id=self.request.query_params['assignee'])
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='change_status')
    def change_status(self, request, pk=None):
        """Смена статуса задачи."""
        task = self.get_object()
        status_id = request.data.get('status_id')
        if not status_id:
            return Response({'detail': 'Не указан статус.'},
                            status=status.HTTP_400_BAD_REQUEST)
        task.status_id = status_id
        # Если статус «выполнено» — проставим время завершения
        new_status = models.TaskStatus.objects.filter(pk=status_id).first()
        if new_status and new_status.code == 'done':
            task.completed_at = timezone.now()
        task.save()
        return Response(serializers.TaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Быстрая отметка задачи как выполненной."""
        task = self.get_object()
        done = models.TaskStatus.objects.filter(code='done').first()
        if done:
            task.status = done
        task.completed_at = timezone.now()
        task.save()
        return Response(serializers.TaskSerializer(task).data)


# ====== Сводка для главного экрана ========================================

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
        if user.is_authenticated and user.is_employee:
            open_tasks = models.Task.objects.exclude(
                status__code__in=['done', 'cancelled']
            )
            if not user.is_admin_or_manager:
                open_tasks = open_tasks.filter(assignee=user)
            data['tasks_open'] = open_tasks.count()
        return Response(data)
