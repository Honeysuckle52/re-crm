-- =============================================================================
-- Откат частично применённой конфликтующей миграции
--   key.0005_task_kind_kpi_outgoing_email
--
-- Зачем:
--   В ветке django-task-model существовали две конфликтующие миграции от
--   общего родителя 0004_propertyphoto_hidden_order:
--
--     * 0005_task_fields_outgoing_email       (вариант A, соответствует models.py)
--     * 0005_task_kind_kpi_outgoing_email     (вариант B, orphan — удалён)
--
--   После `makemigrations --merge` Django попытался применить обе, B прошла
--   успешно и записалась в django_migrations, A упала на дубликате колонки
--   tasks.result. Файл B удалён из репозитория, но в базе остались:
--     * запись в django_migrations о применении миграции B;
--     * колонки tasks.kind, tasks.auto_close_rule, tasks.duration_sec,
--       tasks.result (JSONB);
--     * индексы tasks_assignee_status_idx, tasks_request_kind_idx,
--       tasks_property_kind_idx;
--     * таблицы employee_kpi, outgoing_emails (созданная в схеме B).
--
-- Этот скрипт возвращает БД в состояние после 0004, чтобы 0005 (вариант A)
-- и 0006_merge_* (если был сгенерирован локально) могли применяться начисто.
--
-- Запуск (из каталога simple/):
--   psql -U <USER> -d <DB_NAME> -f scripts/fix_migrations_0005.sql
-- После этого:
--   python manage.py migrate
-- =============================================================================

BEGIN;

-- 1. Снять запись о применённой миграции B.
DELETE FROM django_migrations
 WHERE app  = 'key'
   AND name = '0005_task_kind_kpi_outgoing_email';

-- На случай если локально был сгенерирован merge-файл — его тоже снимаем;
-- файл вы можете удалить руками (это артефакт `makemigrations --merge`).
DELETE FROM django_migrations
 WHERE app  = 'key'
   AND name LIKE '0006_merge_%';

-- 2. Убрать индексы, добавленные миграцией B (если существуют).
DROP INDEX IF EXISTS tasks_assignee_status_idx;
DROP INDEX IF EXISTS tasks_request_kind_idx;
DROP INDEX IF EXISTS tasks_property_kind_idx;

-- 3. Снять колонки, которых нет в моделях варианта A.
ALTER TABLE tasks DROP COLUMN IF EXISTS kind;
ALTER TABLE tasks DROP COLUMN IF EXISTS auto_close_rule;
ALTER TABLE tasks DROP COLUMN IF EXISTS duration_sec;

-- 4. Колонка result в B — JSONB, в A — TEXT. Сбрасываем её, чтобы
--    миграция A создала её заново как TEXT без конфликта типов.
ALTER TABLE tasks DROP COLUMN IF EXISTS result;

-- 5. employee_kpi — модель есть только в orphan-коде, таблица не нужна.
DROP TABLE IF EXISTS employee_kpi CASCADE;

-- 6. outgoing_emails — таблица создана в схеме B (template/body_text/...).
--    Модель в models.py описывает другую схему (recipient/sender/body/...),
--    поэтому дропаем — миграция A создаст её с нужной структурой.
DROP TABLE IF EXISTS outgoing_emails CASCADE;

COMMIT;

-- =============================================================================
-- После успешного выполнения запустите:
--   python manage.py migrate
-- Ожидаемый вывод:
--   Applying key.0005_task_fields_outgoing_email... OK
-- =============================================================================
