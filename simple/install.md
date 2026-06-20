1. Требования
Обязательные компоненты:

Python 3.10–3.12 (рекомендуется 3.11)

pip 23+

PostgreSQL 13+ (основная БД)

Node.js 18 LTS или новее

npm 9+

База данных:

PostgreSQL 13+ — рекомендуется для разработки и обязателен для production

Опциональные компоненты:

DaData API ключ для подсказок адресов

2GIS API ключ для обогащения объектов недвижимости

SMTP-сервер для email-уведомлений

2. Клонирование и настройка окружения
Клонирование репозитория:

bash
git clone <url-репозитория> re-crm
cd re-crm
Создание виртуального окружения:

Windows (PowerShell):

powershell
python -m venv .venv
.venv\Scripts\activate

bash
pip install -r requirements.txt
3. Настройка .env
Создание файла конфигурации:

bash
cp .env.example .env
Основные настройки:

env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_VITE_DEV_MODE=True
Настройка базы данных — PostgreSQL:

env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=re_crm
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
Создание базы данных:

# Windows (через psql)
psql -U postgres -c "CREATE DATABASE re_crm;"
Для SQLite (только разработка):

env
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
API-ключи (опционально):

env
DADATA_API_KEY=your_dadata_api_key
TWOGIS_API_KEY=your_2gis_api_key
Настройка почты (опционально):

env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.yandex.ru
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=your-email@yandex.ru
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@yandex.ru
Для отладки используйте консольный бэкенд:

env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
Реквизиты агентства (для PDF-договоров):

env
AGENCY_LEGAL_NAME=ООО «РИЭЛТ-Сервис»
AGENCY_ADDRESS=г. Москва, ул. Тверская, д. 1
AGENCY_PHONE=+7 (495) 123-45-67
AGENCY_INN=7701234567
AGENCY_KPP=770101001
AGENCY_OGRN=1234567890123
AGENCY_BANK_DETAILS=р/с 40702810123456789012 в ПАО Сбербанк, к/с 30101810400000000225, БИК 044525225
AGENCY_SIGNATORY_NAME=Иванов Иван Иванович
AGENCY_SIGNATORY_TITLE=Генеральный директор
AGENCY_SIGNATORY_BASIS=Устав

4. Миграции и демо-данные
Применение миграций:

bash
python manage.py migrate
Создание суперпользователя:

bash
python manage.py createsuperuser
Заполнение демо-данными:

bash
python manage.py seed_data
Команда создаст справочники (статусы, типы операций, роли), тестовых пользователей с разными ролями, объекты недвижимости (с обогащением через 2GIS при наличии ключа), заявки, сделки и задачи.

5. Настройка фронтенда
Установка зависимостей:

bash
cd frontend
npm install
Режим разработки (с HMR):

bash
npm run dev
Vite-сервер запустится на http://localhost:5173

Сборка для production:

bash
npm run build
Собранные файлы попадут в frontend/dist.

Сборка статики для Django:

bash
cd ..
python manage.py collectstatic --noinput
Важно: для production в .env установите:

env
DJANGO_VITE_DEV_MODE=False
6. Запуск приложения
Минимальный запуск (без фонового воркера):

bash
python manage.py runserver
Приложение доступно по адресу: http://127.0.0.1:8000

Запуск с фоновым воркером (рекомендуется):

bash
python manage.py runserver
Воркер очереди (process_background_jobs) запускается автоматически.

Отключение воркера:

bash
python manage.py runserver --without-worker
Ручной запуск воркера в отдельном терминале:

bash
python manage.py process_background_jobs --loop
Доступ к интерфейсам:

Основное SPA-приложение: http://127.0.0.1:8000

Django Admin: http://127.0.0.1:8000/admin

7. Фоновые задачи и очередь
Воркер обрабатывает:

Email-уведомления (подтверждение регистрации, назначение задач, закрытие заявок)

Генерацию PDF-договоров

Без запущенного воркера письма и договоры останутся в статусе pending.

Проверка статуса воркера:

bash
python manage.py process_background_jobs --status
8. Тестирование
Backend-тесты (Django):

bash
python manage.py test
E2E-тесты (Playwright):

Установка Playwright:

bash
cd frontend
npx playwright install
Запуск тестов:

bash
npx playwright test
Тесты ожидают, что бэкенд и Vite-сервер запущены.

9. Production-развёртывание
Настройки для production:

В .env установите:

env
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DJANGO_VITE_DEV_MODE=False
Сборка статики:

bash
cd frontend
npm run build
cd ..
python manage.py collectstatic --noinput
Настройка веб-сервера (пример для Nginx):

nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static/ {
        alias /path/to/re-crm/static/;
    }
    
    location /media/ {
        alias /path/to/re-crm/media/;
    }
}
Запуск через Gunicorn:

bash
gunicorn simple.wsgi:application --workers 4 --bind 127.0.0.1:8000
Настройка воркера как systemd-сервиса:

Создайте /etc/systemd/system/re-crm-worker.service:

ini
[Unit]
Description=РИЭЛТ CRM Background Worker
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/re-crm
ExecStart=/path/to/re-crm/.venv/bin/python manage.py process_background_jobs --loop
Restart=always

[Install]
WantedBy=multi-user.target
Запуск и включение сервиса:

bash
sudo systemctl enable re-crm-worker
sudo systemctl start re-crm-worker

10. Нагрузочное тестирование
Подготовка тестовых пользователей:

bash
python manage.py seed_loadtest_users --count 120
Установка k6: скачайте с официального сайта или через пакетный менеджер.

Запуск теста авторизации:

bash
k6 run simple/loadtests/k6-auth-login.js --env BASE_URL=http://127.0.0.1:8000 --env VUS=10 --env USER_COUNT=120
Доступные уровни нагрузки: 10, 25, 50, 100, 200 VU.

Результаты сохраняются в simple/loadtests/results/auth-login-summary.json.

11. Типичные проблемы и решения
Симптом	Решение
ModuleNotFoundError	Активируйте виртуальное окружение: .venv\Scripts\activate
Ошибка подключения к БД	Проверьте параметры в .env, убедитесь, что PostgreSQL запущен
Миграции не применяются	python manage.py migrate --fake-initial
Не отображается фронтенд	Запустите npm run build и collectstatic, проверьте DJANGO_VITE_DEV_MODE
Письма не отправляются	Для отладки: EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
PDF-договор не генерируется	Проверьте реквизиты в .env, статус воркера: python manage.py process_background_jobs --status
404 на статику	Выполните python manage.py collectstatic --noinput
Очередь не обрабатывается	Запустите воркер: python manage.py process_background_jobs --loop
CORS-ошибки	Проверьте CORS_ALLOWED_ORIGINS в .env

12. Чеклист установки
Python 3.10–3.12 установлен

Виртуальное окружение создано и активировано

Зависимости установлены (pip install -r requirements.txt)

.env создан и настроен

PostgreSQL установлен и запущен

База данных создана

Миграции выполнены (python manage.py migrate)

Демо-данные загружены (python manage.py seed_data)

Суперпользователь создан (python manage.py createsuperuser)

Фронтенд собран (cd frontend && npm install && npm run build)

Статика собрана (python manage.py collectstatic --noinput)

Сервер запущен (python manage.py runserver)

Админка доступна по http://127.0.0.1:8000/admin

Воркер запущен для фоновых задач

13. Полезные команды
bash
# Показать все URL-ы
python manage.py show_urls

# Очистка кэша
python manage.py clear_cache

# Проверка работоспособности
python manage.py check

# Интерактивная оболочка Django
python manage.py shell

# Создание резервной копии БД
python manage.py dbbackup

# Восстановление БД из резервной копии
python manage.py dbrestore

14. Структура проекта (кратко)
text
simple/                # Django-проект
├── key/               # Основное приложение CRM/ERP
│   ├── models.py      # Модели данных
│   ├── views.py       # API-эндпоинты
│   ├── serializers.py # DRF-сериализаторы
│   └── ...            # Сервисы (аудит, отчёты, документы и т.д.)
├── templates/         # Шаблоны Django
├── static/            # Статические файлы
└── frontend/          # Vue 3 SPA
    ├── src/           # Исходники фронтенда
    ├── tests/         # E2E-тесты Playwright
    └── dist/          # Сборка для production