# РИЭЛТ — учётная система агентства недвижимости (Django + Vue)

CRM/ERP-шаблон для агентства недвижимости: Django 6 + DRF на бэкенде,
Vue 3 + Pinia + Vite на фронтенде, PostgreSQL в качестве хранилища,
подсказки адресов — DaData (через открытый ключ), авторизация — JWT.

## Суть CRM/ERP в этом проекте

Система строится по классической модели агентства недвижимости:

- **CRM-контур (работа с клиентами).** Пользователи → заявки → показы →
  сделки. Клиент регистрируется самостоятельно, но без выбора роли.
  Тип учётной записи и должность назначает администратор или менеджер
  через отдельный эндпоинт и интерфейс. У клиента свой «вид» данных —
  он видит только свои заявки, сделки и просмотры.
- **ERP-контур (внутренняя работа агентства).** Объекты недвижимости,
  их статусы и история изменений, документы, фотографии, характеристики,
  воронка сделок (статусы: «открыта» → «переговоры» → «договор» →
  «завершена» / «отменена»), а также задачи сотрудников (звонок, показ,
  документы) с приоритетами, исполнителями и сроками.
- **Разделение прав.** Три роли сотрудников — администратор, менеджер,
  агент. Агент работает только со своими заявками/задачами;
  администратор и менеджер видят всё и распоряжаются назначениями.
  Клиент — только «свой» срез данных.

## Структура

```
simple/                   ← корень проекта
├── simple/               ← Django-проект (settings, urls, wsgi)
├── key/                  ← Django-приложение CRM/ERP
│   ├── models.py            — ORM-модели (справочники, адреса,
│   │                          пользователи, объекты, сделки, задачи)
│   ├── serializers.py       — сериализаторы DRF
│   ├── views.py             — ViewSet-ы + APIView (аутентификация,
│   │                          прокси к DaData, сводка дашборда)
│   ├── permissions.py       — права доступа по ролям
│   ├── dadata.py            — клиент сервиса подсказок DaData
│   ├── urls.py              — маршруты REST API
│   ├── admin.py             — админка Django
│   └── management/commands/seed_dictionaries.py — наполнение справочников
├── frontend/             ← Vue 3 + Vite (django-vite)
│   └── src/
│       ├── main.js, router.js, api.js
│       ├── store/auth.js          — Pinia-хранилище токенов и прав
│       ├── views/                 — экраны (Сводка, Объекты, Заявки,
│       │                            Задачи, Сделки, Пользователи, …)
│       ├── components/            — TopBar, PropertyCard, StatCard,
│       │                            AddressAutocomplete (DaData)
│       └── styles/main.css        — единая дизайн-система
├── templates/index.html  ← Django-шаблон с точкой монтирования Vue
├── manage.py
├── requirements.txt
└── .env.example
```

## Почему именно так

- **Папка проекта `simple`, приложение `key`** — сохранены из исходной
  структуры, менять названия пакетов не требуется.
- **3НФ-схема БД** реализована на уровне Django-моделей
  (`key/models.py`) с явными именами таблиц в `Meta.db_table`.
  `python manage.py migrate` строит таблицы один в один.
- **Кастомная модель пользователя** (`AbstractBaseUser` + `PermissionsMixin`)
  нужна, потому что в проекте есть `user_type`, `phone`,
  `is_email_verified`, `role` и т. п.
- **JWT (`djangorestframework-simplejwt`)** — токен-аутентификация
  с ротацией и чёрным списком refresh-токенов.
- **Подсказки адресов — DaData.** Ключ хранится только в `.env`
  на сервере, клиент обращается к прокси-эндпоинту
  `/api/dadata/suggest-address/`. Изображения и характеристики объектов
  вводятся сотрудником вручную — DaData даёт только адресные данные.
- **Регистрация без выбора роли.** `RegisterSerializer` принимает только
  `username`, `email`, `phone`, `password`, и всегда создаёт клиента
  без должности. Назначение роли делает администратор или менеджер
  через `/api/users/{id}/assign_role/`.
- **`django-vite`** подключает сборку Vue как обычный статический ассет,
  сохраняя single-project / single-template схему.

## Запуск

### 1. Бэкенд

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # заполните креды PostgreSQL и DADATA_API_KEY
createdb re_crm                      # или через pgAdmin / psql

python manage.py migrate
python manage.py seed_dictionaries   # наполнение справочников
python manage.py createsuperuser
python manage.py runserver
```

Админка: http://127.0.0.1:8000/admin/

### 2. Фронтенд

```bash
cd frontend
npm install
npm run dev                           # Vite dev-сервер на :5173 с HMR
```

Открываем **http://127.0.0.1:8000/** — Django отдаёт шаблон,
а `{% vite_asset %}` подключает модули с dev-сервера Vite.

### 3. Сборка под прод

```bash
cd frontend && npm run build
# в .env выставить DJANGO_VITE_DEV_MODE=False
python manage.py collectstatic --noinput
```

## API (основное)

| Метод | URL                                         | Описание                                      |
|-------|---------------------------------------------|-----------------------------------------------|
| POST  | `/api/auth/register/`                       | Регистрация (всегда клиент, без роли)         |
| POST  | `/api/auth/login/`                          | Логин → `{access, refresh}`                   |
| POST  | `/api/auth/refresh/`                        | Обновление `access`                           |
| GET   | `/api/auth/me/`                             | Текущий пользователь                          |
| GET   | `/api/dadata/suggest-address/?q=...`        | Подсказки адресов через DaData                |
| CRUD  | `/api/users/`                               | Пользователи (список для сотрудников)         |
| POST  | `/api/users/{id}/assign_role/`              | Назначить тип и должность (админ/менеджер)    |
| CRUD  | `/api/properties/`                          | Объекты недвижимости                          |
| POST  | `/api/properties/{id}/change_status/`       | Смена статуса + запись в историю              |
| POST  | `/api/properties/{id}/upload_photo/`        | Загрузка фото (файл или внешняя ссылка)       |
| GET   | `/api/properties/{id}/history/`             | История статусов                              |
| CRUD  | `/api/property-photos/`                     | Фото объектов                                 |
| CRUD  | `/api/property-features/`                   | Справочник характеристик                      |
| CRUD  | `/api/requests/`                            | Заявки клиентов                               |
| POST  | `/api/requests/{id}/close/`                 | Закрыть заявку                                |
| CRUD  | `/api/deals/`                               | Сделки                                        |
| POST  | `/api/deals/{id}/change_status/`            | Смена статуса сделки (воронка)                |
| CRUD  | `/api/tasks/`                               | Задачи сотрудников                            |
| POST  | `/api/tasks/{id}/change_status/`            | Смена статуса задачи                          |
| POST  | `/api/tasks/{id}/complete/`                 | Быстро пометить задачу как выполненную        |
| CRUD  | `/api/cities/`, `/api/streets/`, `/api/houses/`, `/api/addresses/` | Адресная иерархия |
| GET   | `/api/dashboard/stats/`                     | Сводка для главного экрана                    |

## Безопасность

- Ключ DaData живёт **только в `.env`** на сервере, в заголовок
  `Authorization: Token <api-key>` подставляется на серверной стороне.
- Пароли хешируются PBKDF2 (стандарт Django).
- Доступ к защищённым эндпоинтам — только с действующим JWT.
- Разграничение прав: сотрудник редактирует, клиент только читает
  собственные данные, назначать должности может только администратор
  или менеджер.
- CORS ограничен доверенными origins.
