"""Регистрация моделей в админке Django."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from . import models


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone', 'user_type',
                    'role', 'is_active', 'created_at')
    list_filter = ('user_type', 'role', 'is_active')
    search_fields = ('username', 'email', 'phone')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Контакты', {'fields': ('email', 'phone')}),
        ('Тип и роль', {'fields': ('user_type', 'role')}),
        ('Подтверждение', {'fields': ('is_email_verified', 'is_phone_verified')}),
        ('Права', {'fields': ('is_active', 'is_staff', 'is_superuser',
                              'groups', 'user_permissions')}),
        ('Активность', {'fields': ('last_login', 'last_ip')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2',
                       'user_type', 'role'),
        }),
    )


admin.site.register(models.OperationType)
admin.site.register(models.PropertyStatus)
admin.site.register(models.RequestStatus)
admin.site.register(models.DealStatus)
admin.site.register(models.TaskStatus)
admin.site.register(models.UserRole)
admin.site.register(models.City)
admin.site.register(models.Street)
admin.site.register(models.House)
admin.site.register(models.Address)
admin.site.register(models.EmployeeProfile)
admin.site.register(models.ClientProfile)
admin.site.register(models.PropertyFeature)


class PropertyPhotoInline(admin.TabularInline):
    model = models.PropertyPhoto
    extra = 1
    fields = ('image', 'url', 'caption', 'is_cover')


class PropertyFeatureValueInline(admin.TabularInline):
    model = models.PropertyFeatureValue
    extra = 1


@admin.register(models.Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'operation_type', 'status',
                    'price', 'rooms_count', 'created_at')
    list_filter = ('operation_type', 'status', 'rooms_count')
    search_fields = ('title', 'description')
    inlines = [PropertyPhotoInline, PropertyFeatureValueInline]


@admin.register(models.Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'agent', 'operation_type',
                    'status', 'created_at')
    list_filter = ('operation_type', 'status')


@admin.register(models.Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ('deal_number', 'property', 'client', 'agent',
                    'status', 'price_final', 'deal_date')
    list_filter = ('status', 'operation_type')
    search_fields = ('deal_number',)


@admin.register(models.Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'priority', 'assignee',
                    'due_date', 'created_at')
    list_filter = ('status', 'priority', 'assignee')
    search_fields = ('title', 'description')


admin.site.register(models.PropertyStatusHistory)
admin.site.register(models.PropertyViewing)
admin.site.register(models.PropertyDocument)
