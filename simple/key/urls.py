"""URL-маршруты приложения ``key``."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenRefreshView,
    TokenVerifyView,
)

from . import views

router = DefaultRouter()

router.register('operation-types', views.OperationTypeViewSet)
router.register('property-statuses', views.PropertyStatusViewSet)
router.register('request-statuses', views.RequestStatusViewSet)
router.register('deal-statuses', views.DealStatusViewSet)
router.register('task-statuses', views.TaskStatusViewSet)
router.register('notification-templates', views.NotificationTemplateViewSet)
router.register('process-versions', views.ProcessVersionViewSet)
router.register('user-roles', views.UserRoleViewSet)

router.register('cities', views.CityViewSet)
router.register('streets', views.StreetViewSet)
router.register('houses', views.HouseViewSet)
router.register('addresses', views.AddressViewSet)

router.register('users', views.UserViewSet)
router.register('employee-profiles', views.EmployeeProfileViewSet)
router.register('client-profiles', views.ClientProfileViewSet)

router.register('properties', views.PropertyViewSet)
router.register('property-features', views.PropertyFeatureViewSet)
router.register('property-photos', views.PropertyPhotoViewSet)
router.register('property-documents', views.PropertyDocumentViewSet)

router.register('requests', views.RequestViewSet)
router.register('request-matches', views.RequestPropertyMatchViewSet,
                basename='request-matches')
router.register('deals', views.DealViewSet)
router.register('viewings', views.PropertyViewingViewSet)
router.register('tasks', views.TaskViewSet)
router.register('outgoing-emails', views.OutgoingEmailViewSet)
router.register('audit-log', views.AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', TokenBlacklistView.as_view(), name='logout'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/me/', views.MeView.as_view(), name='me'),

    path('dadata/suggest-address/',
         views.DadataSuggestAddressView.as_view(),
         name='dadata_suggest_address'),

    path('dashboard/stats/', views.DashboardStatsView.as_view(),
         name='dashboard_stats'),
    path('properties/export/', views.PropertyExportView.as_view(),
         name='property_export'),
    path('dictionaries/export/', views.DictionaryExportView.as_view(),
         name='dictionary_export'),
    path('reports/deals/', views.DealsReportView.as_view(),
         name='deals_report'),
    path('reports/tasks/', views.TasksReportView.as_view(),
         name='tasks_report'),

    path('', include(router.urls)),
]
