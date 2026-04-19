"""
Спринт 2: расширение задач для движка автозакрытия + сущности KPI
и журнала исходящих писем.

1. ``Task.kind`` / ``auto_close_rule`` / ``result`` / ``duration_sec`` —
   поля, необходимые движку доменных событий в ``signals.py`` и
   статистике.
2. ``EmployeeKPI`` — дневной агрегат по типам задач.
3. ``OutgoingEmail`` — журнал исходящих писем с клиентам
   (автоматическое уведомление «подобран подходящий объект»
   и ручные ретраи при сбоях SMTP).

Миграция НЕ меняет уже существующие данные — новые поля задач
получают безопасные дефолты (`kind='other'`, `result={}`), записи
в `EmployeeKPI` / `OutgoingEmail` создаются впоследствии движком.
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('key', '0004_propertyphoto_hidden_order'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---------------- Task: расширение -------------------------------
        migrations.AddField(
            model_name='task',
            name='kind',
            field=models.CharField(
                max_length=30,
                default='other',
                db_index=True,
                choices=[
                    ('call',            'Звонок клиенту'),
                    ('client_search',   'Поиск клиентов для объекта'),
                    ('property_search', 'Подбор объектов для клиента'),
                    ('viewing',         'Показ объекта'),
                    ('documents',       'Подготовка документов'),
                    ('follow_up',       'Повторный контакт'),
                    ('other',           'Прочее'),
                ],
                help_text=('Тип задачи — используется для автозакрытия '
                           'и статистики.'),
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='auto_close_rule',
            field=models.CharField(
                max_length=40,
                blank=True, null=True,
                choices=[
                    ('on_client_matched',   'Когда подобран клиент для объекта'),
                    ('on_property_matched', 'Когда подобран объект для клиента'),
                    ('on_viewing_done',     'Когда показ проведён'),
                    ('on_deal_created',     'Когда создана сделка'),
                    ('on_request_closed',   'Когда заявка закрыта'),
                ],
                help_text=('Код доменного события, автоматически '
                           'закрывающего задачу.'),
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='result',
            field=models.JSONField(
                default=dict, blank=True,
                help_text=('Результат выполнения (что именно сделано, '
                           'автор, контекст).'),
            ),
        ),
        migrations.AddField(
            model_name='task',
            name='duration_sec',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(
                fields=['assignee', 'status'],
                name='tasks_assignee_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(
                fields=['request', 'kind'],
                name='tasks_request_kind_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(
                fields=['property', 'kind'],
                name='tasks_property_kind_idx',
            ),
        ),

        # ---------------- EmployeeKPI ------------------------------------
        migrations.CreateModel(
            name='EmployeeKPI',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False)),
                ('period', models.DateField(
                    help_text=('Дата, к которой относится запись '
                               '(день завершения задачи).'))),
                ('kind', models.CharField(max_length=30, default='other',
                    choices=[
                        ('call',            'Звонок клиенту'),
                        ('client_search',   'Поиск клиентов для объекта'),
                        ('property_search', 'Подбор объектов для клиента'),
                        ('viewing',         'Показ объекта'),
                        ('documents',       'Подготовка документов'),
                        ('follow_up',       'Повторный контакт'),
                        ('other',           'Прочее'),
                    ])),
                ('completed_count', models.PositiveIntegerField(default=0)),
                ('auto_closed_count', models.PositiveIntegerField(default=0)),
                ('overdue_count', models.PositiveIntegerField(default=0)),
                ('total_duration_sec', models.BigIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='kpi_rows',
                    limit_choices_to={'user_type': 'employee'},
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'employee_kpi',
                'verbose_name': 'KPI сотрудника',
                'verbose_name_plural': 'KPI сотрудников',
                'ordering': ['-period', 'employee_id'],
                'unique_together': {('employee', 'period', 'kind')},
                'indexes': [
                    models.Index(fields=['employee', 'period'],
                                 name='employee_kpi_emp_period_idx'),
                ],
            },
        ),

        # ---------------- OutgoingEmail ----------------------------------
        migrations.CreateModel(
            name='OutgoingEmail',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False)),
                ('template', models.CharField(max_length=60)),
                ('to_email', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=255)),
                ('body_text', models.TextField()),
                ('body_html', models.TextField(blank=True)),
                ('status', models.CharField(max_length=15, default='queued',
                    choices=[
                        ('queued',    'В очереди'),
                        ('sent',      'Отправлено'),
                        ('failed',    'Ошибка'),
                        ('cancelled', 'Отменено'),
                    ])),
                ('error', models.TextField(blank=True, null=True)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField()),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('to_user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='incoming_emails',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('related_task', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='outgoing_emails',
                    to='key.task',
                )),
                ('related_request', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='outgoing_emails',
                    to='key.request',
                )),
                ('related_property', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='outgoing_emails',
                    to='key.property',
                )),
            ],
            options={
                'db_table': 'outgoing_emails',
                'verbose_name': 'Исходящее письмо',
                'verbose_name_plural': 'Исходящие письма',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', 'created_at'],
                                 name='outgoing_emails_status_idx'),
                    models.Index(fields=['related_request'],
                                 name='outgoing_emails_request_idx'),
                    models.Index(fields=['related_task'],
                                 name='outgoing_emails_task_idx'),
                ],
            },
        ),
    ]
