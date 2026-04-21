"""
Добавляем журнал этапов выполнения задачи.

Сотрудник проходит несколько шагов (позвонил → оформил заявку →
подобрал объект → завершил), и теперь каждый шаг сохраняется
в JSON-поле ``Task.steps_log``. Это нужно:
* чтобы в окне /tasks/:id/work рендерить прогресс-степпер;
* чтобы в истории выполненных задач показывать, что именно
  сделал сотрудник;
* чтобы отчёты и KPI могли анализировать «до какого шага дошёл».

Поле безопасное и обратно-совместимое: старые задачи остаются с
пустым списком и продолжают работать без изменений.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('key', '0002_dealstatus_taskstatus_alter_propertyphoto_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='steps_log',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text=(
                    'Журнал этапов выполнения: список объектов '
                    '{step, outcome, note, at, by}. Заполняется через '
                    'action /tasks/{id}/record_step/.'
                ),
            ),
        ),
    ]
