"""
Настройки проекта «Учётная система агентства недвижимости».
Django 6 + DRF + JWT + PostgreSQL + django-vite + Vue 3.
"""
from datetime import timedelta
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

# --- Core -------------------------------------------------------------------

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-me')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # сторонние
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_vite',
    'drf_spectacular',

    # локальные
    'key',
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

# --- База данных (PostgreSQL) -----------------------------------------------

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

# --- Аутентификация ---------------------------------------------------------

AUTH_USER_MODEL = 'key.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- Локализация ------------------------------------------------------------

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# --- Статика и медиа --------------------------------------------------------

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

# --- DRF --------------------------------------------------------------------

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
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
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

# --- CORS -------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
CORS_ALLOW_CREDENTIALS = True

# --- django-vite ------------------------------------------------------------

DJANGO_VITE = {
    'default': {
        'dev_mode': os.getenv('DJANGO_VITE_DEV_MODE', 'True').lower() == 'true',
        'dev_server_host': os.getenv('DJANGO_VITE_DEV_SERVER_HOST', '127.0.0.1'),
        'dev_server_port': int(os.getenv('DJANGO_VITE_DEV_SERVER_PORT', '5173')),
        'manifest_path': BASE_DIR / 'frontend' / 'dist' / '.vite' / 'manifest.json',
        'static_url_prefix': '/static/',
    }
}

# --- DaData (подсказки адресов) --------------------------------------------
#
# Используется открытый API подсказок DaData. Ключ хранится ТОЛЬКО на сервере
# и в браузер не передаётся — запросы идут через прокси-эндпоинт
# /api/dadata/suggest-address/. Значение по умолчанию — ключ из ТЗ,
# на продакшне обязательно переопределяйте через переменную окружения.

DADATA_API_URL = os.getenv(
    'DADATA_API_URL',
    'https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address',
)
DADATA_API_KEY = os.getenv('DADATA_API_KEY', '')

# --- Email (SMTP) ----------------------------------------------------------
#
# Рабочий почтовый ящик агентства для автоматических писем клиентам.
# Все параметры читаются из переменных окружения, чтобы не хранить
# пароли в репозитории.
#
#   EMAIL_HOST           — SMTP-сервер провайдера (например, smtp.yandex.ru)
#   EMAIL_PORT           — 465 для SSL, 587 для STARTTLS
#   EMAIL_USE_SSL        — True для 465
#   EMAIL_USE_TLS        — True для 587
#   EMAIL_HOST_USER      — логин (обычно полный адрес ящика)
#   EMAIL_HOST_PASSWORD  — «пароль приложения», не основной пароль
#   DEFAULT_FROM_EMAIL   — адрес-отправитель («Агентство <info@...>»)
#   AGENCY_REPLY_TO      — куда клиент ответит (обычно = EMAIL_HOST_USER)
#
# Если EMAIL_HOST не задан — автоматически включается консольный backend
# (письма пишутся в stdout), чтобы разработчик видел тело письма без
# настройки SMTP.

EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() == 'true'
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '15'))

DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    EMAIL_HOST_USER or 'noreply@example.com',
)
AGENCY_REPLY_TO = os.getenv('AGENCY_REPLY_TO', EMAIL_HOST_USER)
AGENCY_NAME = os.getenv('AGENCY_NAME', 'Агентство недвижимости')
# Внешний публичный URL — подставляется в ссылки в письмах.
AGENCY_PUBLIC_URL = os.getenv('AGENCY_PUBLIC_URL', 'http://localhost:5173')

EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
    if EMAIL_HOST else
    'django.core.mail.backends.console.EmailBackend'
)
