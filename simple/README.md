# Simple — CRM/ERP недвижимости (Django + Vue)

Проект-шаблон для агентства недвижимости: бэкенд на Django + DRF,
фронтенд на Vue 3, связка через `django-vite`, БД — PostgreSQL,
адресная интеграция — ФИАС (master-token), авторизация — JWT.

## Структура

```
/                      ← корень проекта
├── simple/            ← Django-проект (settings, urls, wsgi)
├── key/               ← Django-приложение (models, views, serializers, admin, fias)
├── frontend/          ← Vue 3 + Vite (django-vite)
│   └── src/
│       ├── main.js, router.js, api.js
│       ├── store/auth.js     ← Pinia-хранилище JWT
│       ├── views/            ← экраны (Dashboard, Properties, Requests, …)
│       ├── components/       ← TopBar, PropertyCard, StatCard, …
│       └── styles/main.css   ← дизайн-система мокапа
├── templates/index.html      ← Django-шаблон с точкой монтирования Vue
├── key/management/commands/  ← management-команды (seed_dictionaries)
├── manage.py
├── requirements.txt
└── .env.example
```

## Почему именно так

- **Папка проекта `simple`, приложение `key`** — ровно как вы просили.
- **Модели Django (`key/models.py`) 1-в-1 повторяют 3НФ-схему** из PDF
  (имена таблиц через `Meta.db_table`). Переходить на сырой SQL не нужно
  — `python manage.py migrate` построит идентичные таблицы.
- **Кастомный `User`** (`AbstractBaseUser` + `PermissionsMixin`) вместо
  стандартного, т. к. в схеме требуется `user_type`, `phone`, `is_email_verified`
  и т. д. Это единственное осознанное отклонение от «чистого стандарта»
  Django: без кастомной модели нельзя соблюсти ТЗ.
- **JWT (`djangorestframework-simplejwt`)** — токен-аутентификация.
  Refresh-ротация, blacklist, автообновление access в Axios-интерсепторе.
- **ФИАС-клиент (`key/fias.py`)** использует заголовок `master-token`
  согласно требованиям публичного сервиса ФНС.
  Токен живёт только в `.env` на сервере — в браузер не передаётся.
- **`django-vite`** подключает сборку Vue как обычный статический ассет,
  сохраняя single-project / single-template схему.

## Запуск

### 1. Бэкенд

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # заполните креды PostgreSQL и FIAS_API_TOKEN
createdb simple_crm               # или через pgAdmin / psql

python manage.py makemigrations key
python manage.py migrate
python manage.py seed_dictionaries            # наполнение справочников
python manage.py createsuperuser
python manage.py runserver
```

Админка: http://127.0.0.1:8000/admin/
Swagger: http://127.0.0.1:8000/api/docs/

### 2. Фронтенд

```bash
cd frontend
npm install
npm run dev       # Vite dev-server на :5173 с HMR
```

Открываем **http://127.0.0.1:8000/** — Django отдаст шаблон,
а `{% vite_asset %}` подключит модули с dev-сервера Vite.

### 3. Production-сборка

```bash
cd frontend && npm run build
# В .env выставить DJANGO_VITE_DEV_MODE=False
python manage.py collectstatic --noinput
```

## API (основное)

| Метод | URL                                 | Описание                              |
|-------|-------------------------------------|---------------------------------------|
| POST  | `/api/auth/register/`               | Регистрация                           |
| POST  | `/api/auth/login/`                  | Логин → `{access, refresh}` JWT       |
| POST  | `/api/auth/refresh/`                | Обновление access                     |
| GET   | `/api/auth/me/`                     | Текущий пользователь                  |
| GET   | `/api/fias/search/?q=...`           | Поиск адреса через ФИАС               |
| CRUD  | `/api/properties/`                  | Объекты недвижимости                  |
| POST  | `/api/properties/{id}/change_status/` | Смена статуса + запись в историю    |
| GET   | `/api/properties/{id}/history/`     | История статусов                      |
| CRUD  | `/api/requests/`                    | Заявки клиентов                       |
| POST  | `/api/requests/{id}/close/`         | Закрыть заявку                        |
| CRUD  | `/api/deals/`                       | Сделки                                |
| CRUD  | `/api/cities/`, `/api/streets/`, `/api/houses/`, `/api/addresses/` | Адресная иерархия |
| GET   | `/api/dashboard/stats/`             | Сводка для главного экрана            |

Полная спецификация — Swagger на `/api/docs/`.

## Безопасность (как требует ФИАС)

- Токен `master-token` ФИАС живёт **только в `.env`**, на сервере,
  передаётся в заголовке ровно так, как описано на fias.nalog.ru.
- Клиент обращается к `/api/fias/search/`, а не к ФИАС напрямую.
- Пароли хешируются PBKDF2 (стандарт Django).
- CORS ограничен доверенными origins.
- RLS на уровне БД легко добавить через миграции.
