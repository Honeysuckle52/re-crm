"""Настройки проекта."""
# -*- coding: utf-8 -*-
from datetime import timedelta
from pathlib import Path
import json
import os

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name: str, default: str = '') -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


def env_json(name: str, default):
    raw = os.getenv(name)
    if raw in (None, ''):
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImproperlyConfigured(f'{name} must contain valid JSON.') from exc


SECRET_KEY = os.getenv('SECRET_KEY', '')
DEBUG = env_bool('DEBUG', True)
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '')

if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY must be set in environment.')
if not DEBUG and SECRET_KEY.startswith('django-insecure'):
    raise ImproperlyConfigured('Use a strong SECRET_KEY when DEBUG=False.')
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS must be set when DEBUG=False.')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'key',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_vite',
    'drf_spectacular',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'simple.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'simple.wsgi.application'
ASGI_APPLICATION = 'simple.asgi.application'

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv('DB_NAME', 're_crm'),
        "USER": os.getenv('DB_USER', 'postgres'),
        "PASSWORD": os.getenv('DB_PASSWORD', 'postgre'),
        "HOST": os.getenv('DB_HOST', 'localhost'),
        "PORT": os.getenv('DB_PORT', '5432'),
        "OPTIONS": {"client_encoding": "UTF8"},
    }
}

AUTH_USER_MODEL = 'key.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Irkutsk'
USE_I18N = True
USE_TZ = True
FILE_CHARSET = 'utf-8'
DEFAULT_CHARSET = 'utf-8'

VITE_ASSETS_DIR = BASE_DIR / "frontend" / "dist" / ".vite"

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'frontend' / 'dist',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATABASE_BACKUP_ROOT = Path(
    os.getenv('DATABASE_BACKUP_ROOT', BASE_DIR / 'private_backups'),
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'key.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Учётная система агентства недвижимости',
    'DESCRIPTION': 'API управления объектами недвижимости, заявками и сделками',
    'VERSION': '1.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
ENABLE_API_DOCS = env_bool('ENABLE_API_DOCS', DEBUG)

default_cors_origins = (
    'http://localhost:5173,http://127.0.0.1:5173,'
    'http://localhost:8000,http://127.0.0.1:8000'
) if DEBUG else ''
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS', default_cors_origins)
CORS_ALLOW_CREDENTIALS = env_bool('CORS_ALLOW_CREDENTIALS', True)
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

DJANGO_VITE = {
    'default': {
        'dev_mode': env_bool('DJANGO_VITE_DEV_MODE', DEBUG),
        'dev_server_host': os.getenv('DJANGO_VITE_DEV_SERVER_HOST', '127.0.0.1'),
        'dev_server_port': int(os.getenv('DJANGO_VITE_DEV_SERVER_PORT', '5173')),
        'manifest_path': BASE_DIR / 'frontend' / 'dist' / '.vite' / 'manifest.json',
        'static_url_prefix': '/static/',
    }
}

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.yandex.ru')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '465'))
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', True)
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', False)

# SSL приоритетнее TLS, иначе Django падает на старте.
if EMAIL_USE_SSL and EMAIL_USE_TLS:
    EMAIL_USE_TLS = False

EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '30'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@example.com')
EMAIL_VERIFICATION_CODE_TTL_MINUTES = int(
    os.getenv('EMAIL_VERIFICATION_CODE_TTL_MINUTES', '15'),
)
EMAIL_FALLBACK_ENABLED = env_bool('EMAIL_FALLBACK_ENABLED', EMAIL_USE_SSL)
EMAIL_FALLBACK_BACKEND = os.getenv('EMAIL_FALLBACK_BACKEND', EMAIL_BACKEND)
EMAIL_FALLBACK_HOST = os.getenv('EMAIL_FALLBACK_HOST', EMAIL_HOST)
EMAIL_FALLBACK_PORT = int(
    os.getenv(
        'EMAIL_FALLBACK_PORT',
        '587' if EMAIL_PORT == 465 else str(EMAIL_PORT),
    ),
)
EMAIL_FALLBACK_USE_SSL = os.getenv(
    'EMAIL_FALLBACK_USE_SSL',
    'False',
).lower() in {'1', 'true', 'yes', 'on'}
EMAIL_FALLBACK_USE_TLS = os.getenv(
    'EMAIL_FALLBACK_USE_TLS',
    'True' if EMAIL_USE_SSL else str(EMAIL_USE_TLS),
).lower() in {'1', 'true', 'yes', 'on'}
if EMAIL_FALLBACK_USE_SSL and EMAIL_FALLBACK_USE_TLS:
    EMAIL_FALLBACK_USE_TLS = False
EMAIL_FALLBACK_TIMEOUT = int(
    os.getenv('EMAIL_FALLBACK_TIMEOUT', str(EMAIL_TIMEOUT)),
)
EMAIL_FALLBACK_USER = os.getenv('EMAIL_FALLBACK_USER', EMAIL_HOST_USER)
EMAIL_FALLBACK_PASSWORD = os.getenv(
    'EMAIL_FALLBACK_PASSWORD',
    EMAIL_HOST_PASSWORD,
)

AGENCY_NAME = os.getenv('AGENCY_NAME', 'Агентство недвижимости')
AGENCY_LEGAL_NAME = os.getenv('AGENCY_LEGAL_NAME', AGENCY_NAME)
AGENCY_PUBLIC_URL = os.getenv('AGENCY_PUBLIC_URL', '')
AGENCY_REPLY_TO = os.getenv('AGENCY_REPLY_TO', EMAIL_HOST_USER)
AGENCY_PHONE = os.getenv('AGENCY_PHONE', '')
AGENCY_ADDRESS = os.getenv('AGENCY_ADDRESS', '')
AGENCY_INN = os.getenv('AGENCY_INN', '')
AGENCY_KPP = os.getenv('AGENCY_KPP', '')
AGENCY_OGRN = os.getenv('AGENCY_OGRN', '')
AGENCY_BANK_DETAILS = os.getenv('AGENCY_BANK_DETAILS', '')
AGENCY_SIGNATORY_NAME = os.getenv('AGENCY_SIGNATORY_NAME', '')
AGENCY_SIGNATORY_TITLE = os.getenv('AGENCY_SIGNATORY_TITLE', '')
AGENCY_SIGNATORY_BASIS = os.getenv(
    'AGENCY_SIGNATORY_BASIS',
    'внутренних документов Исполнителя',
)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', not DEBUG)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', not DEBUG)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = os.getenv('X_FRAME_OPTIONS', 'DENY')
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = env_bool('CSRF_COOKIE_HTTPONLY', False)
REFERRER_POLICY = os.getenv('REFERRER_POLICY', 'same-origin')

DADATA_API_URL = os.getenv(
    'DADATA_API_URL',
    'https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address',
)
DADATA_API_KEY = os.getenv(
    'DADATA_API_KEY',
    '',
)

# 2GIS Places API — обогащение объектов недвижимости данными и фото.
TWOGIS_API_KEY = os.getenv('TWOGIS_API_KEY', '')
SMARTPAY_TOKEN = os.getenv('SMARTPAY_TOKEN', '')
SMARTPAY_SERVICE_ID = os.getenv('SMARTPAY_SERVICE_ID', '')
SMARTPAY_AMOUNT = int(os.getenv('SMARTPAY_AMOUNT', '100'))
SMARTPAY_TIMEOUT = int(os.getenv('SMARTPAY_TIMEOUT', '15'))
SMARTPAY_API_BASE_URL = os.getenv('SMARTPAY_API_BASE_URL', 'https://api.smartmarket.tech/v1/')
SMARTPAY_CREATE_INVOICE_PATH = os.getenv('SMARTPAY_CREATE_INVOICE_PATH', 'invoices/')
SMARTPAY_STATUS_PATH_TEMPLATE = os.getenv('SMARTPAY_STATUS_PATH_TEMPLATE', 'invoices/{invoice_id}/')
SMARTPAY_REFUND_PATH_TEMPLATE = os.getenv('SMARTPAY_REFUND_PATH_TEMPLATE', 'invoices/{invoice_id}/refund/')

BACKGROUND_AUTORUN_ENABLED = env_bool('BACKGROUND_AUTORUN_ENABLED', True)
BACKGROUND_AUTORUN_LIMIT = int(os.getenv('BACKGROUND_AUTORUN_LIMIT', '10'))
BACKGROUND_AUTORUN_MAX_PASSES = int(os.getenv('BACKGROUND_AUTORUN_MAX_PASSES', '3'))
