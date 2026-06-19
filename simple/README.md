# РИЭЛТ — учётная система агентства недвижимости (Django + Vue)

CRM/ERP-шаблон для агентства недвижимости: Django 6 + DRF на бэкенде,
Vue 3 + Pinia + Vite на фронтенде, PostgreSQL в качестве хранилища,
подсказки адресов — DaData, обогащение объектов — 2GIS, авторизация — JWT.

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
  Клиент — только «свой» срез данных. В роли также хранятся лимиты
  нагрузки: активные заявки, активные задачи и задачи «в работе».
- **Журнал действий и отчётность.** Все ключевые операции пишутся в
  единый аудит-лог (`key/audit.py`), а сервис отчётов (`key/reports.py`)
  и слой импорта/экспорта (`key/data_exchange.py`) дают выгрузки в
  CSV/XLSX без внешних зависимостей.

## Структура

```
simple/
├── manage.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── simple/                              ← Django-проект
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── key/                                 ← Django-приложение CRM/ERP
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── audit.py
│   ├── business_rules.py
│   ├── dadata.py
│   ├── data_exchange.py
│   ├── db_backups.py
│   ├── deals_service.py
│   ├── documents.py
│   ├── email_verification.py
│   ├── events.py
│   ├── export_formatting.py
│   ├── mailing.py
│   ├── models.py
│   ├── pagination.py
│   ├── permissions.py
│   ├── reports.py
│   ├── request_lifecycle.py
│   ├── seeding.py
│   ├── serializers.py
│   ├── storage.py
│   ├── task_actions.py
│   ├── task_workflow.py
│   ├── tests.py
│   ├── twogis.py
│   ├── urls.py
│   ├── views.py
│   ├── xlsx_utils.py
│   ├── fonts/
│   │   ├── DejaVuSans.ttf
│   │   ├── DejaVuSans-Bold.ttf
│   │   ├── times.ttf
│   │   ├── timesbd.ttf
│   │   ├── timesbi.ttf
│   │   └── timesi.ttf
│   ├── management/
│   │   ├── __init__.py
│   │   ├── background_worker.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── process_background_jobs.py
│   │       ├── runserver.py
│   │       └── seed_data.py
│   └── templatetags/
│       ├── __init__.py
│       └── vite.py
├── static/                              
│   └── admin/
│       └── css/
│           └── custom_admin.css
├── templates/                           ← HTML-шаблоны и переопределения Django-admin
│   ├── index.html
│   ├── admin/
│   │   ├── backups.html
│   │   ├── base_site.html
│   │   ├── index.html
│   │   ├── nav_sidebar.html
│   │   └── reports.html
│   └── emails/
│       ├── _base.html
│       ├── email_verification/
│       │   ├── body.html
│       │   ├── body.txt
│       │   └── subject.txt
│       ├── property_matched/
│       │   ├── body.html
│       │   ├── body.txt
│       │   └── subject.txt
│       ├── request_closed/
│       │   ├── body.html
│       │   ├── body.txt
│       │   └── subject.txt
│       ├── request_taken/
│       │   ├── body.html
│       │   ├── body.txt
│       │   └── subject.txt
│       ├── task_assigned/
│       │   ├── body.html
│       │   ├── body.txt
│       │   └── subject.txt
│       ├── task_assigned_call/
│       │   ├── body.html
│       │   ├── body.txt
│       │   └── subject.txt
│       ├── task_assigned_documents/
│       │   ├── body.html
│       │   ├── body.txt
│       │   └── subject.txt
│       └── task_assigned_showing/
│           ├── body.html
│           ├── body.txt
│           └── subject.txt
└── frontend/                            ← Vue 3 + Vite SPA
    ├── index.html
    ├── package-lock.json
    ├── package.json
    ├── playwright.config.js
    ├── pnpm-lock.yaml
    ├── vite.config.js
    ├── tests/
    │   └── e2e/
    │       └── register.spec.js
    └── src/
        ├── App.vue
        ├── main.js
        ├── router.js
        ├── api/
        │   ├── audit.js
        │   ├── bulk.js
        │   ├── exports.js
        │   ├── index.js
        │   └── tasks.js
        ├── components/
        │   ├── AddressAutocomplete.vue
        │   ├── AppFooter.vue
        │   ├── AuditLogPanel.vue
        │   ├── BulkActionBar.vue
        │   ├── ConfirmHost.vue
        │   ├── CurrentTaskWidget.vue
        │   ├── DataFetchPanel.vue
        │   ├── DictionaryManager.vue
        │   ├── InfoRow.vue
        │   ├── ListPagination.vue
        │   ├── NetworkBanner.vue
        │   ├── PropertyCard.vue
        │   ├── PropertyPickerModal.vue
        │   ├── RemoteLookupField.vue
        │   ├── RequestCloseDialog.vue
        │   ├── StatCard.vue
        │   ├── TaskMineBadge.vue
        │   ├── ToastHost.vue
        │   └── TopBar.vue
        ├── composables/
        │   ├── useBulkSelection.js
        │   ├── useDraftPersistence.js
        │   ├── useFloatingFooterOffset.js
        │   ├── useNetworkStatus.js
        │   ├── useUnsavedChangesGuard.js
        │   └── useVisibilityRefresh.js
        ├── store/
        │   ├── auth.js
        │   ├── confirm.js
        │   ├── toasts.js
        │   └── workload.js
        ├── styles/
        │   └── main.css
        ├── utils/
        │   ├── deals.js
        │   ├── downloads.js
        │   ├── formatters.js
        │   ├── paginated.js
        │   ├── propertyTypes.js
        │   └── requestClose.js
        └── views/
            ├── Account.vue
            ├── Admin.vue
            ├── Clients.vue
            ├── Dashboard.vue
            ├── DealDetail.vue
            ├── Deals.vue
            ├── Login.vue
            ├── Properties.vue
            ├── PropertyDetail.vue
            ├── PropertyForm.vue
            ├── PropertyModeration.vue
            ├── Register.vue
            ├── Reports.vue
            ├── RequestDetail.vue
            ├── Requests.vue
            ├── TaskWorkflow.vue
            └── Tasks.vue
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
- **Подсказки адресов — DaData, обогащение объектов — 2GIS.** Ключ хранится
  только в `.env` на сервере, клиент обращается к прокси-эндпоинту
  `/api/dadata/suggest-address/`. При создании объекта сервер может подтянуть
  из 2GIS координаты, краткое описание и карты.
- **Регистрация без выбора роли.** `RegisterSerializer` принимает
  `username`, `email`, `phone`, `password`, а также обязательные
  `first_name` и `last_name`; учётная запись всегда создаётся как клиент
  без должности. Назначение роли делает администратор или менеджер
  через `/api/users/{id}/assign_role/`.
- **`django-vite`** подключает сборку Vue как обычный статический ассет,
  сохраняя single-project / single-template схему.
- **XLSX без сторонних библиотек.** Чтение и запись Excel-файлов
  выполняет собственный модуль `key/xlsx_utils.py`, чтобы не тянуть
  тяжёлые зависимости вроде `openpyxl`.

## Запуск

### 1. Бэкенд

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # заполните креды PostgreSQL, SECRET_KEY, DADATA_API_KEY и TWOGIS_API_KEY
createdb re_crm                      # или через pgAdmin / psql

python manage.py migrate
python manage.py makemigrations
python manage.py seed_data
python manage.py createsuperuser
python manage.py runserver           # worker process_background_jobs стартует автоматически
# если worker нужно отключить:
# python manage.py runserver --without-worker
```

Для почты можно задать резервный SMTP-канал через `EMAIL_FALLBACK_*`.
Это полезно, если основной `465/SSL` подвисает на handshake, а
`587/STARTTLS` работает стабильнее.

Для корректного оформления PDF-договоров заполните в `.env` реквизиты
агентства:

- `AGENCY_LEGAL_NAME`
- `AGENCY_ADDRESS`
- `AGENCY_PHONE`
- `AGENCY_INN`
- `AGENCY_KPP`
- `AGENCY_OGRN`
- `AGENCY_BANK_DETAILS`
- `AGENCY_SIGNATORY_NAME`
- `AGENCY_SIGNATORY_TITLE`
- `AGENCY_SIGNATORY_BASIS`

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

### 4. End-to-end тесты (Playwright)

```bash
cd frontend
npx playwright install                # один раз
npx playwright test                   # запускает сценарии из tests/e2e/
```

Конфиг — `frontend/playwright.config.js`. Тесты ожидают, что бэкенд и
Vite-dev-сервер уже подняты.

## API (основное)

| Метод | URL                                         | Описание                                      |
|-------|---------------------------------------------|-----------------------------------------------|
| POST  | `/api/auth/register/`                       | Регистрация (всегда клиент, без роли)         |
| POST  | `/api/auth/login/`                          | Логин → `{access, refresh}`                   |
| POST  | `/api/auth/logout/`                         | Logout и blacklist текущего `refresh`         |
| POST  | `/api/auth/refresh/`                        | Обновление `access`                           |
| GET   | `/api/auth/me/`                             | Текущий пользователь                          |
| GET   | `/api/dadata/suggest-address/?q=...`        | Подсказки адресов через DaData                |
| CRUD  | `/api/users/`                               | Пользователи (список для сотрудников)         |
| CRUD  | `/api/user-roles/`                          | Роли сотрудников и лимиты нагрузки            |
| CRUD  | `/api/operation-types/`                     | Справочник типов операций                     |
| CRUD  | `/api/property-statuses/`                   | Справочник статусов объектов                  |
| CRUD  | `/api/request-statuses/`                    | Справочник статусов заявок                    |
| CRUD  | `/api/deal-statuses/`                       | Справочник статусов сделок                    |
| CRUD  | `/api/task-statuses/`                       | Справочник статусов задач                     |
| POST  | `/api/users/{id}/assign_role/`              | Назначить тип и должность (админ/менеджер)    |
| CRUD  | `/api/properties/`                          | Объекты недвижимости                          |
| POST  | `/api/properties/{id}/change_status/`       | Смена статуса + запись в историю              |
| POST  | `/api/properties/{id}/upload_photo/`        | Загрузка фото (файл или внешняя ссылка)       |
| GET   | `/api/properties/{id}/history/`             | История статусов                              |
| CRUD  | `/api/property-photos/`                     | Фото объектов                                 |
| CRUD  | `/api/property-features/`                   | Справочник характеристик                      |
| CRUD  | `/api/requests/`                            | Заявки клиентов                               |
| POST  | `/api/requests/{id}/close/`                 | Закрыть заявку с `outcome`                    |
| CRUD  | `/api/deals/`                               | Сделки                                        |
| GET   | `/api/deals/{id}/contract/`                | Скачать PDF-договор или получить статус очереди |
| POST  | `/api/deals/{id}/regenerate_contract/`     | Поставить генерацию договора в очередь        |
| POST  | `/api/deals/{id}/change_status/`            | Смена статуса сделки (воронка)                |
| CRUD  | `/api/tasks/`                               | Задачи сотрудников                            |
| POST  | `/api/tasks/{id}/change_status/`            | Смена статуса задачи                          |
| POST  | `/api/tasks/{id}/complete/`                 | Быстро пометить задачу как выполненную        |
| GET   | `/api/audit-log/`                           | Журнал действий пользователей                 |
| GET   | `/api/reports/...`                          | Отчёты и выгрузки в CSV/XLSX                  |
| POST  | `/api/data-exchange/import/`                | Импорт справочников и данных                  |
| GET   | `/api/data-exchange/export/`                | Экспорт справочников и данных                 |
| POST  | `/api/bulk/...`                             | Массовые операции над списками                |
| CRUD  | `/api/cities/`, `/api/streets/`, `/api/houses/`, `/api/addresses/` | Адресная иерархия |
| GET   | `/api/dashboard/stats/`                     | Сводка для главного экрана                    |

Списочные эндпоинты используют постраничную выдачу
`StandardResultsSetPagination` (`key/pagination.py`).

## Безопасность

- Для `POST /api/requests/{id}/close/` ожидается тело вида
  `{ "outcome": "completed|cancelled|rejected|lost" }`.
- Ключ DaData живёт **только в `.env`** на сервере, в заголовок
  `Authorization: Token <api-key>` подставляется на серверной стороне.
- Пароли хешируются PBKDF2 (стандарт Django).
- Доступ к защищённым эндпоинтам — только с действующим JWT.
- Разграничение прав: сотрудник редактирует, клиент только читает
  собственные данные, назначать должности может только администратор
  или менеджер.
- CORS ограничен доверенными origins.
- Все изменения значимых сущностей фиксируются в журнале действий
  через `key/audit.py`.

## Фоновые задания

- Письма и PDF-договоры не отправляются прямо из HTTP-запроса.
  API только ставит их в БД-очередь.
- Для обработки очереди нужно держать отдельный процесс:

```bash
python manage.py process_background_jobs --loop
```

- Без воркера письма останутся в статусе `pending`, а договоры —
  в статусах `pending` / `processing`.
- `GET /api/deals/{id}/contract/` возвращает `409`, если договор ещё
  формируется или предыдущая попытка завершилась ошибкой.
- При SMTP-таймаутах воркер может автоматически переключиться на
  резервный канал из `EMAIL_FALLBACK_*`.
- `key/documents.py` строит PDF-договор через ReportLab на базе
  данных сделки, объекта, клиента и агентства; суммы выводятся
  цифрами и прописью, а реквизиты Исполнителя берутся из `.env`.

## Назначение файлов

### Корень

- **manage.py** — точка входа Django CLI.
- **requirements.txt** — зависимости Python.
- **.env.example** — шаблон переменных окружения.
- **.gitignore** — исключения для git.
- **README.md** — этот файл.

### `simple/` (Django-проект)

- **__init__.py** — маркер пакета.
- **settings.py** — настройки Django (БД, приложения, middleware).
- **urls.py** — корневой роутер URL.
- **asgi.py** — ASGI-точка входа.
- **wsgi.py** — WSGI-точка входа.

### `key/` (приложение CRM)

- **__init__.py** — маркер пакета.
- **admin.py** — регистрация моделей в Django-admin.
- **apps.py** — конфиг приложения.
- **audit.py** — сервис записи единого журнала действий пользователей.
- **business_rules.py** — бизнес-правила (валидации, расчёты).
- **dadata.py** — клиент сервиса подсказок DaData.
- **data_exchange.py** — импорт и экспорт данных CRM (CSV/XLSX).
- **deals_service.py** — сервис сделок и очередь генерации PDF-договоров.
- **email_verification.py** — сервис подтверждения email и кода верификации.
- **documents.py** — генерация PDF-договоров через ReportLab.
- **events.py** — журнал доменных событий.
- **export_formatting.py** — форматирование данных перед экспортом.
- **mailing.py** — очередь и отправка email-уведомлений.
- **models.py** — ORM-модели (User, Property, Request, Deal, Task и т. д.).
- **pagination.py** — общий класс DRF-пагинации для списочных эндпоинтов.
- **permissions.py** — DRF-пермишены по ролям.
- **reports.py** — сервисный слой отчётов и экспортов.
- **request_lifecycle.py** — единый жизненный цикл заявки и побочных эффектов.
- **seeding.py** — общий слой заполнения справочников, demo-данных и 2GIS-обогащения.
- **serializers.py** — DRF-сериализаторы.
- **task_actions.py** — операции над задачами (старт/пауза/завершение).
- **task_workflow.py** — серверная схема этапов и переходов workflow задач.
- **tests.py** — модульные тесты.
- **urls.py** — URL-роутер приложения.
- **views.py** — DRF ViewSet'ы и API-эндпоинты.
- **xlsx_utils.py** — минимальный XLSX reader/writer без внешних зависимостей.
- **fonts/DejaVuSans.ttf**, **DejaVuSans-Bold.ttf**, **times.ttf**, **timesbd.ttf**, **timesbi.ttf**, **timesi.ttf** — шрифты с кириллицей для PDF.
- **management/background_worker.py** — общие helper'ы для dev-запуска background worker (значения по умолчанию и сборка команды `process_background_jobs --loop`); используется `runserver.py` и тестами.
- **management/commands/__init__.py** — маркер пакета команд.
- **management/commands/process_background_jobs.py** — воркер очереди писем и PDF.
- **management/commands/runserver.py** — dev-runserver с автозапуском background worker.
- **management/commands/seed_data.py** — единая команда заполнения справочников и demo-данных.
- **templatetags/vite.py** — теги шаблонов для подключения Vite-бандла.

### `static/`

- Каталог, в который `collectstatic` собирает финальные ассеты для прод-сборки.

### `templates/`

- **index.html** — корневой HTML, в который монтируется SPA.
- **admin/** — переопределения шаблонов Django-admin.
- **emails/** — шаблоны системных уведомлений.

### `frontend/` (корень SPA)

- **index.html** — HTML-точка входа Vite.
- **package.json**, **package-lock.json**, **pnpm-lock.yaml** — манифест и лок-файлы зависимостей.
- **vite.config.js** — конфиг сборки Vite (alias, прокси).
- **playwright.config.js** — конфиг E2E-тестов Playwright.

### `frontend/tests/`

- **e2e/register.spec.js** — E2E-сценарий регистрации пользователя.

### `frontend/src/`

- **App.vue** — корневой компонент SPA.
- **main.js** — bootstrap Vue/Pinia/Router.
- **router.js** — описание маршрутов.

### `frontend/src/api/`

- **index.js** — axios-инстанс и общие CRUD-эндпоинты.
- **audit.js** — клиент API журнала действий.
- **bulk.js** — клиент API массовых операций.
- **exports.js** — клиент API отчётов и выгрузок (CSV/XLSX).
- **tasks.js** — API задач (старт/пауза/завершение).

### `frontend/src/components/`

- **AddressAutocomplete.vue** — поле адреса с подсказками DaData.
- **AppFooter.vue** — подвал приложения.
- **AuditLogPanel.vue** — панель просмотра журнала действий.
- **BulkActionBar.vue** — плавающая панель массовых действий над списком.
- **ConfirmHost.vue** — глобальный модал подтверждения опасных действий.
- **CurrentTaskWidget.vue** — виджет текущей активной задачи.
- **DataFetchPanel.vue** — обёртка с состояниями загрузки/ошибки/пустого списка.
- **DictionaryManager.vue** — универсальный CRUD-редактор справочников.
- **InfoRow.vue** — строка «label — value» для деталей.
- **ListPagination.vue** — управление постраничной выдачей списков.
- **NetworkBanner.vue** — баннер потери сети / офлайн-режима.
- **PropertyCard.vue** — карточка объекта недвижимости.
- **RemoteLookupField.vue** — поле с серверным поиском по справочнику.
- **RequestCloseDialog.vue** — диалог закрытия заявки с выбором исхода.
- **StatCard.vue** — карточка с числовым показателем.
- **TaskMineBadge.vue** — бейдж «моя задача».
- **ToastHost.vue** — контейнер для toast-уведомлений.
- **TopBar.vue** — верхняя навигационная панель.

### `frontend/src/composables/`

- **useBulkSelection.js** — выбор элементов списка для массовых операций.
- **useDraftPersistence.js** — автосохранение черновика формы в localStorage.
- **useFloatingFooterOffset.js** — расчёт отступа под плавающие панели.
- **useNetworkStatus.js** — отслеживание онлайн/офлайн-статуса браузера.
- **useUnsavedChangesGuard.js** — защита от потери несохранённых изменений.
- **useVisibilityRefresh.js** — авто-обновление данных при возвращении на вкладку.

### `frontend/src/store/`

- **auth.js** — авторизация, токен, профиль пользователя.
- **confirm.js** — состояние глобального диалога подтверждения.
- **toasts.js** — очередь toast-уведомлений.
- **workload.js** — текущая нагрузка агента (активные задачи).

### `frontend/src/styles/`

- **main.css** — глобальные стили и CSS-переменные.

### `frontend/src/utils/`

- **deals.js** — хелперы для работы со сделками (статусы, форматы).
- **downloads.js** — скачивание файлов (PDF/CSV/XLSX) из ответа axios.
- **formatters.js** — общие форматтеры денег и дат.
- **paginated.js** — утилиты для постраничной выдачи списков.
- **propertyTypes.js** — справочник и хелперы по типам объектов.
- **requestClose.js** — формирование payload для закрытия заявки.

### `frontend/src/views/`

- **Account.vue** — личный кабинет пользователя.
- **Admin.vue** — административная панель.
- **Clients.vue** — список клиентов.
- **Dashboard.vue** — главная со сводкой.
- **DealDetail.vue** — детальная карточка сделки.
- **Deals.vue** — список сделок.
- **Login.vue** — страница входа.
- **Properties.vue** — каталог объектов.
- **PropertyDetail.vue** — детальная карточка объекта.
- **PropertyForm.vue** — форма создания/редактирования объекта.
- **Register.vue** — регистрация.
- **Reports.vue** — отчёты и выгрузки.
- **RequestDetail.vue** — детальная карточка заявки.
- **Requests.vue** — список заявок.
- **TaskWorkflow.vue** — пошаговое выполнение задачи.
- **Tasks.vue** — список задач агента.

## Нагрузочное тестирование авторизации

Если нужно буквально прогнать массовую авторизацию пользователей, используйте минимальный `k6`-сценарий:

- скрипт: `simple/loadtests/k6-auth-login.js`
- endpoint: `POST /api/auth/login/`
- ramp-up: `60s`
- длительность плато: `5m`
- think time: `1-3s`
- уровни: `10`, `25`, `50`, `100`, `200` VU

### 1. Подготовить пул пользователей

После `migrate` выполните:

```bash
python manage.py seed_loadtest_users --count 120
```

Будут созданы пользователи `loadtest.user.001@example.com` ... `loadtest.user.120@example.com`.
Пароль по умолчанию для всех: `LoadTestAuth123!`.

### 2. Установить k6

Проверьте, что `k6` доступен:

```bash
k6 version
```

### 3. Запустить тест авторизации

Пример для 10 виртуальных пользователей:

```bash
k6 run simple/loadtests/k6-auth-login.js --env BASE_URL=http://127.0.0.1:8000 --env VUS=10 --env USER_COUNT=120
```

Остальные уровни:

```bash
k6 run simple/loadtests/k6-auth-login.js --env BASE_URL=http://127.0.0.1:8000 --env VUS=25  --env USER_COUNT=120
k6 run simple/loadtests/k6-auth-login.js --env BASE_URL=http://127.0.0.1:8000 --env VUS=50  --env USER_COUNT=120
k6 run simple/loadtests/k6-auth-login.js --env BASE_URL=http://127.0.0.1:8000 --env VUS=100 --env USER_COUNT=120
k6 run simple/loadtests/k6-auth-login.js --env BASE_URL=http://127.0.0.1:8000 --env VUS=200 --env USER_COUNT=120
```

Если сервер работает не на `127.0.0.1:8000`, замените `BASE_URL`.

### 4. Что собирается

`k6` покажет:

- время отклика `min`, `p50`, `p95`, `p99`, `max`
- `RPS`
- процент успешных и неуспешных логинов
- ошибки и таймауты

JSON summary сохраняется в `simple/loadtests/results/auth-login-summary.json`.

### 5. Ресурсы сервера

`k6` сам не снимает `CPU / RAM / I/O` сервера приложения. Их нужно смотреть параллельно во время теста, например:

```powershell
Get-Process python | Select-Object ProcessName,Id,CPU,WS,PM
```

или через `Task Manager` / `Resource Monitor`, либо если приложение запущено в Docker:

```bash
docker stats
```
