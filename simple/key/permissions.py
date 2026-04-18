"""
Права доступа CRM/ERP агентства недвижимости.

Разграничение:
    * администратор (superuser или ``role.code == 'admin'``) — всё;
    * менеджер (``role.code == 'manager'``) — управление пользователями,
      сделками, объектами, заявками;
    * агент (``role.code == 'agent'``) — свои заявки/сделки/просмотры,
      все объекты доступны только на чтение и редактирование своих;
    * клиент (``user_type == 'client'``) — только собственные записи.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


def _authenticated(request) -> bool:
    return bool(request.user and request.user.is_authenticated)


class IsAdminOrManager(BasePermission):
    """Администратор или менеджер агентства."""
    message = 'Требуются права администратора или менеджера.'

    def has_permission(self, request, view):
        if not _authenticated(request):
            return False
        return request.user.is_admin_or_manager


class IsEmployee(BasePermission):
    """Любой сотрудник агентства."""
    message = 'Действие доступно только сотрудникам агентства.'

    def has_permission(self, request, view):
        return _authenticated(request) and request.user.is_employee


class IsEmployeeOrReadOnly(BasePermission):
    """Чтение доступно авторизованным, изменения — только сотрудникам."""

    def has_permission(self, request, view):
        if not _authenticated(request):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_employee


class IsAdminOrManagerOrReadOnly(BasePermission):
    """Чтение — всем авторизованным, запись — только админу/менеджеру."""

    def has_permission(self, request, view):
        if not _authenticated(request):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin_or_manager
