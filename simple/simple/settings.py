"""Настройки проекта."""
from datetime import timedelta
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-me')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

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
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

VITE_ASSETS_DIR = BASE_DIR / "frontend" / "dist" / ".vite"

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'frontend' / 'dist',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

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

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
CORS_ALLOW_CREDENTIALS = True

DJANGO_VITE = {
    'default': {
        'dev_mode': os.getenv('DJANGO_VITE_DEV_MODE', 'True').lower() == 'true',
        'dev_server_host': os.getenv('DJANGO_VITE_DEV_SERVER_HOST', '127.0.0.1'),
        'dev_server_port': int(os.getenv('DJANGO_VITE_DEV_SERVER_PORT', '5173')),
        'manifest_path': BASE_DIR / 'frontend' / 'dist' / '.vite' / 'manifest.json',
        'static_url_prefix': '/static/',
    }
}

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.mail.ru')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '465'))
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'True').lower() == 'true'
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').lower() == 'true'

# SSL приоритетнее TLS, иначе Django падает на старте.
if EMAIL_USE_SSL and EMAIL_USE_TLS:
    EMAIL_USE_TLS = False

EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '30'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'danil_naumov_90@bk.ru')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
EMAIL_FALLBACK_ENABLED = os.getenv('EMAIL_FALLBACK_ENABLED', '').lower() in {
    '1', 'true', 'yes', 'on',
} if os.getenv('EMAIL_FALLBACK_ENABLED') is not None else EMAIL_USE_SSL
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
).lower() == 'true'
EMAIL_FALLBACK_USE_TLS = os.getenv(
    'EMAIL_FALLBACK_USE_TLS',
    'True' if EMAIL_USE_SSL else str(EMAIL_USE_TLS),
).lower() == 'true'
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
AGENCY_PUBLIC_URL = os.getenv('AGENCY_PUBLIC_URL', 'http://127.0.0.1:8000')
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

DADATA_API_URL = os.getenv(
    'DADATA_API_URL',
    'https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address',
)
DADATA_API_KEY = os.getenv(
    'DADATA_API_KEY',
    '8ceded5bba84e0bd3f20cd7a36057324dc680563',
)

# 2GIS Places API — обогащение объектов недвижимости данными и фото.
# Ключ хранится ТОЛЬКО на сервере и никогда не передаётся в браузер.
TWOGIS_API_KEY = os.getenv('TWOGIS_API_KEY', '0e9c9bee-64f5-42fa-b8c6-0925a6d20eef')
