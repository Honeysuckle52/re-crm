"""Регистрация моделей и настройка Django admin."""
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.template.response import TemplateResponse
from django.urls import path

from . import mailing, models, reports


def _crm_admin_has_permission(request):
    user = request.user
    return bool(
        user.is_active
        and user.is_authenticated
        and user.is_staff
        and (
            getattr(user, 'is_superuser', False)
            or getattr(user, 'role_code', None) == 'admin'
        )
    )


admin.site.has_permission = _crm_admin_has_permission
admin.site.site_header = 'РИЭЛТ · Django Admin'
admin.site.site_title = 'РИЭЛТ Admin'
admin.site.index_title = 'Системное администрирование'


def _admin_query_string(query_dict, **updates):
    query = query_dict.copy()
    for key, value in updates.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f'?{encoded}' if encoded else ''


def _build_admin_report_context(request):
    report_type = (request.GET.get('type') or 'deals').strip().lower()
    if report_type not in {'deals', 'tasks'}:
        report_type = 'deals'

    params = request.GET.copy()
    params['type'] = report_type

    if report_type == 'tasks':
        payload = reports.build_tasks_report(params, user=request.user)
        status_options = models.TaskStatus.objects.all()
        ordering_options = reports.TASKS_REPORT.ordering_options
    else:
        payload = reports.build_deals_report(params, user=request.user)
        status_options = models.DealStatus.objects.all()
        ordering_options = reports.DEALS_REPORT.ordering_options

    return report_type, payload, status_options, ordering_options


def _admin_reports_view(request):
    report_type, payload, status_options, ordering_options = _build_admin_report_context(request)
    export_format = (request.GET.get('export') or '').strip().lower()
    if export_format:
        return reports.export_report(
            payload['definition'],
            payload['summary'],
            payload['rows'],
            export_format,
            ordering=payload['ordering'],
        )

    base_query = request.GET.copy()
    base_query['type'] = report_type
    base_query.pop('export', None)

    reset_query = request.GET.copy()
    for key in list(reset_query.keys()):
        reset_query.pop(key, None)
    reset_query['type'] = report_type

    context = {
        **admin.site.each_context(request),
        'title': 'Отчёты',
        'report_type': report_type,
        'report_title': payload['definition'].title,
        'columns': payload['definition'].columns,
        'rows': payload['rows'],
        'table_rows': [
            [
                {'label': label, 'value': row.get(key, '')}
                for key, label in payload['definition'].columns
            ]
            for row in payload['rows']
        ],
        'summary_items': list(payload['summary'].items()),
        'ordering_options': ordering_options,
        'status_options': status_options,
        'employees': models.User.objects.filter(
            user_type='employee',
        ).order_by('username'),
        'task_types': models.Task.TASK_TYPE_CHOICES,
        'filters': {
            'date_from': (request.GET.get('date_from') or '').strip(),
            'date_to': (request.GET.get('date_to') or '').strip(),
            'status': (request.GET.get('status') or '').strip(),
            'ordering': payload['ordering'],
            'agent': (request.GET.get('agent') or '').strip(),
            'assignee': (request.GET.get('assignee') or '').strip(),
            'task_type': (request.GET.get('task_type') or '').strip(),
        },
        'switch_links': {
            'deals': _admin_query_string(base_query, type='deals'),
            'tasks': _admin_query_string(base_query, type='tasks'),
        },
        'reset_link': _admin_query_string(reset_query),
        'export_links': {
            'csv': _admin_query_string(base_query, export='csv'),
            'json': _admin_query_string(base_query, export='json'),
            'xlsx': _admin_query_string(base_query, export='xlsx'),
            'pdf': _admin_query_string(base_query, export='pdf'),
        },
    }
    return TemplateResponse(request, 'admin/reports.html', context)


def _admin_dashboard_view(request):
    return admin.site.index(
        request,
        extra_context={'title': 'Системная админ-панель'},
    )


if not hasattr(admin.site, '_crm_original_get_urls'):
    admin.site._crm_original_get_urls = admin.site.get_urls


def _crm_admin_get_urls():
    custom_urls = [
        path(
            'dashboard/',
            admin.site.admin_view(_admin_dashboard_view),
            name='crm_dashboard',
        ),
        path(
            'reports/',
            admin.site.admin_view(_admin_reports_view),
            name='crm_reports',
        ),
    ]
    return custom_urls + admin.site._crm_original_get_urls()


admin.site.get_urls = _crm_admin_get_urls


class CrmAdminPermissionsMixin:
    """Разрешает полный доступ в Django admin пользователям с ролью admin."""

    list_per_page = 40
    list_max_show_all = 200
    save_on_top = True

    def _has_crm_access(self, request):
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_active
            and user.is_staff
            and (
                getattr(user, 'is_superuser', False)
                or getattr(user, 'role_code', None) == 'admin'
            )
        )

    def has_module_permission(self, request):
        return self._has_crm_access(request)

    def has_view_permission(self, request, obj=None):
        return self._has_crm_access(request)

    def has_add_permission(self, request):
        return self._has_crm_access(request)

    def has_change_permission(self, request, obj=None):
        return self._has_crm_access(request)

    def has_delete_permission(self, request, obj=None):
        return self._has_crm_access(request)


class CodeNameAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(models.OperationType)
class OperationTypeAdmin(CodeNameAdmin):
    pass


@admin.register(models.PropertyStatus)
class PropertyStatusAdmin(CodeNameAdmin):
    pass


@admin.register(models.RequestStatus)
class RequestStatusAdmin(CodeNameAdmin):
    pass


@admin.register(models.DealStatus)
class DealStatusAdmin(CodeNameAdmin):
    list_display = ('code', 'name', 'order')
    list_editable = ('order',)
    ordering = ('order', 'code')


@admin.register(models.TaskStatus)
class TaskStatusAdmin(CodeNameAdmin):
    list_display = ('code', 'name', 'order')
    list_editable = ('order',)
    ordering = ('order', 'code')


@admin.register(models.UserRole)
class UserRoleAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'max_active_tasks',
        'max_in_progress_tasks',
        'max_active_requests',
    )
    list_editable = (
        'max_active_tasks',
        'max_in_progress_tasks',
        'max_active_requests',
    )
    search_fields = ('code', 'name', 'description')
    ordering = ('code',)


@admin.register(models.User)
class UserAdmin(CrmAdminPermissionsMixin, BaseUserAdmin):
    list_display = (
        'username',
        'email',
        'phone',
        'user_type',
        'role',
        'is_active',
        'is_staff',
        'created_at',
    )
    list_filter = ('user_type', 'role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'phone')
    ordering = ('-created_at',)
    list_select_related = ('role',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Контакты', {'fields': ('email', 'phone')}),
        ('Тип и роль', {'fields': ('user_type', 'role')}),
        ('Подтверждение', {'fields': ('is_email_verified', 'is_phone_verified')}),
        (
            'Права',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        ('Активность', {'fields': ('last_login', 'last_ip')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'username',
                    'email',
                    'password1',
                    'password2',
                    'user_type',
                    'role',
                ),
            },
        ),
    )


@admin.register(models.City)
class CityAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('name', 'region', 'external_id')
    search_fields = ('name', 'region')
    ordering = ('name',)


@admin.register(models.Street)
class StreetAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('name', 'street_type', 'city', 'external_id')
    list_filter = ('city',)
    search_fields = ('name', 'city__name')
    list_select_related = ('city',)


@admin.register(models.House)
class HouseAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('street', 'house_number', 'building', 'structure', 'postal_code')
    list_filter = ('street__city',)
    search_fields = ('street__name', 'house_number', 'postal_code')
    list_select_related = ('street', 'street__city')


@admin.register(models.Address)
class AddressAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('house', 'apartment_number', 'entrance', 'floor')
    list_filter = ('house__street__city',)
    search_fields = ('house__street__name', 'house__house_number', 'apartment_number')
    list_select_related = ('house', 'house__street', 'house__street__city')


@admin.register(models.EmployeeProfile)
class EmployeeProfileAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('user', 'last_name', 'first_name', 'position', 'department')
    search_fields = ('user__username', 'first_name', 'last_name', 'position', 'department')
    list_select_related = ('user',)


@admin.register(models.ClientProfile)
class ClientProfileAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('user', 'last_name', 'first_name', 'preferred_contact_method')
    search_fields = ('user__username', 'first_name', 'last_name', 'passport_number')
    list_select_related = ('user',)


@admin.register(models.PropertyFeature)
class PropertyFeatureAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)


class PropertyPhotoInline(admin.TabularInline):
    model = models.PropertyPhoto
    extra = 0
    fields = ('image', 'url', 'caption', 'is_cover', 'is_hidden', 'order')


class PropertyFeatureValueInline(admin.TabularInline):
    model = models.PropertyFeatureValue
    extra = 0


@admin.register(models.Property)
class PropertyAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'operation_type',
        'status',
        'price',
        'rooms_count',
        'created_at',
    )
    list_filter = ('operation_type', 'status', 'rooms_count')
    search_fields = ('title', 'description')
    list_select_related = ('operation_type', 'status')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [PropertyPhotoInline, PropertyFeatureValueInline]


@admin.register(models.Request)
class RequestAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'client',
        'agent',
        'operation_type',
        'status',
        'created_at',
        'closed_at',
    )
    list_filter = ('operation_type', 'status')
    search_fields = ('client__username', 'agent__username', 'description')
    list_select_related = ('client', 'agent', 'operation_type', 'status')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    autocomplete_fields = ('client', 'agent', 'property')


@admin.register(models.Deal)
class DealAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'deal_number',
        'property',
        'client',
        'agent',
        'status',
        'price_final',
        'contract_status',
        'deal_date',
    )
    list_filter = ('status', 'operation_type', 'contract_status')
    search_fields = ('deal_number', 'client__username', 'agent__username')
    list_select_related = ('property', 'client', 'agent', 'status', 'operation_type')
    date_hierarchy = 'deal_date'
    ordering = ('-deal_date', '-id')
    autocomplete_fields = ('property', 'client', 'agent', 'request')


@admin.register(models.Task)
class TaskAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'task_type',
        'status',
        'priority',
        'assignee',
        'due_date',
        'created_at',
    )
    list_filter = ('status', 'priority', 'assignee', 'task_type')
    search_fields = ('title', 'description', 'assignee__username')
    list_select_related = ('status', 'assignee')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    autocomplete_fields = ('assignee', 'created_by', 'client', 'property', 'request', 'deal')


@admin.register(models.PropertyStatusHistory)
class PropertyStatusHistoryAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('property', 'status', 'changed_by', 'changed_at')
    list_filter = ('status', 'changed_at')
    search_fields = ('property__title', 'changed_by__username')
    list_select_related = ('property', 'status', 'changed_by')
    date_hierarchy = 'changed_at'
    ordering = ('-changed_at',)
    autocomplete_fields = ('property', 'changed_by')


@admin.register(models.PropertyViewing)
class PropertyViewingAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('property', 'client', 'agent', 'scheduled_date', 'created_at')
    list_filter = ('scheduled_date', 'agent')
    search_fields = ('property__title', 'client__username', 'agent__username')
    list_select_related = ('property', 'client', 'agent')
    date_hierarchy = 'scheduled_date'
    ordering = ('-scheduled_date',)
    autocomplete_fields = ('property', 'client', 'agent')


@admin.register(models.PropertyDocument)
class PropertyDocumentAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'property',
        'document_name',
        'is_verified',
        'verified_by',
        'uploaded_at',
    )
    list_filter = ('is_verified', 'uploaded_at')
    search_fields = ('document_name', 'property__title', 'verified_by__username')
    list_select_related = ('property', 'verified_by')
    date_hierarchy = 'uploaded_at'
    ordering = ('-uploaded_at',)
    autocomplete_fields = ('property', 'verified_by')


@admin.register(models.OutgoingEmail)
class OutgoingEmailAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'recipient',
        'subject',
        'trigger_code',
        'status',
        'created_at',
        'sent_at',
    )
    list_filter = ('status', 'trigger_code', 'created_at')
    search_fields = ('subject', 'recipient__email', 'recipient__username')
    list_select_related = ('recipient', 'sender')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'processing_started_at', 'sent_at')
    autocomplete_fields = ('recipient', 'sender', 'task', 'request', 'property')
    actions = ('resend_failed_messages',)

    @admin.action(description='Переотправить выбранные письма')
    def resend_failed_messages(self, request, queryset):
        queued = 0
        for email in queryset:
            mailing.resend(email)
            queued += 1
        self.message_user(
            request,
            f'Писем поставлено в очередь повторно: {queued}',
            level=messages.SUCCESS,
        )


@admin.register(models.AuditLog)
class AuditLogAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'created_at',
        'entity_type',
        'entity_id',
        'action_label',
        'actor',
    )
    list_filter = ('entity_type', 'action_code', 'created_at')
    search_fields = ('action_label', 'message', 'actor__username')
    list_select_related = ('actor', 'property', 'request', 'task', 'deal')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = (
        'entity_type',
        'entity_id',
        'action_code',
        'action_label',
        'message',
        'metadata',
        'actor',
        'property',
        'request',
        'task',
        'deal',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
