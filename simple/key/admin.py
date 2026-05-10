"""Регистрация моделей и настройка Django admin."""
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from . import mailing, models


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


class CrmAdminPermissionsMixin:
    """Разрешает полный доступ в Django admin пользователям с ролью admin."""

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


@admin.register(models.House)
class HouseAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('street', 'house_number', 'building', 'structure', 'postal_code')
    list_filter = ('street__city',)
    search_fields = ('street__name', 'house_number', 'postal_code')


@admin.register(models.Address)
class AddressAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('house', 'apartment_number', 'entrance', 'floor')
    list_filter = ('house__street__city',)
    search_fields = ('house__street__name', 'house__house_number', 'apartment_number')


@admin.register(models.EmployeeProfile)
class EmployeeProfileAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('user', 'last_name', 'first_name', 'position', 'department')
    search_fields = ('user__username', 'first_name', 'last_name', 'position', 'department')


@admin.register(models.ClientProfile)
class ClientProfileAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('user', 'last_name', 'first_name', 'preferred_contact_method')
    search_fields = ('user__username', 'first_name', 'last_name', 'passport_number')


@admin.register(models.PropertyFeature)
class PropertyFeatureAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(models.ProcessVersion)
class ProcessVersionAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'process_code',
        'scope_code',
        'version',
        'name',
        'is_active',
        'updated_at',
    )
    list_filter = ('process_code', 'scope_code', 'is_active')
    search_fields = ('name', 'description', 'scope_code')
    ordering = ('process_code', 'scope_code', '-version')
    readonly_fields = ('created_at', 'updated_at')
    actions = ('activate_versions',)

    @admin.action(description='Сделать выбранные версии активными')
    def activate_versions(self, request, queryset):
        activated = 0
        for version in queryset:
            models.ProcessVersion.objects.filter(
                process_code=version.process_code,
                scope_code=version.scope_code,
            ).exclude(pk=version.pk).update(is_active=False)
            version.is_active = True
            version.save(update_fields=['is_active', 'updated_at'])
            activated += 1
        self.message_user(request, f'Активировано версий: {activated}', level=messages.SUCCESS)


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
    inlines = [PropertyPhotoInline, PropertyFeatureValueInline]


@admin.register(models.Request)
class RequestAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'client',
        'agent',
        'operation_type',
        'status',
        'process_version',
        'created_at',
        'closed_at',
    )
    list_filter = ('operation_type', 'status', 'process_version')
    search_fields = ('client__username', 'agent__username', 'description')
    autocomplete_fields = ('client', 'agent', 'property', 'process_version')


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
        'process_version',
        'due_date',
        'created_at',
    )
    list_filter = ('status', 'priority', 'assignee', 'task_type', 'process_version')
    search_fields = ('title', 'description', 'assignee__username')
    autocomplete_fields = ('assignee', 'created_by', 'client', 'property', 'request', 'deal', 'process_version')


@admin.register(models.PropertyStatusHistory)
class PropertyStatusHistoryAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('property', 'status', 'changed_by', 'changed_at')
    list_filter = ('status', 'changed_at')
    search_fields = ('property__title', 'changed_by__username')
    autocomplete_fields = ('property', 'changed_by')


@admin.register(models.PropertyViewing)
class PropertyViewingAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('property', 'client', 'agent', 'scheduled_date', 'created_at')
    list_filter = ('scheduled_date', 'agent')
    search_fields = ('property__title', 'client__username', 'agent__username')
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
    autocomplete_fields = ('property', 'verified_by')


@admin.register(models.NotificationTemplate)
class NotificationTemplateAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'updated_at')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(models.OutgoingEmail)
class OutgoingEmailAdmin(CrmAdminPermissionsMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'recipient',
        'subject',
        'trigger_code',
        'template_code',
        'status',
        'created_at',
        'sent_at',
    )
    list_filter = ('status', 'trigger_code', 'template_code', 'created_at')
    search_fields = ('subject', 'recipient__email', 'recipient__username')
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
