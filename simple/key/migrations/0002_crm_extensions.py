"""
Миграция 0002 — переход от ФИАС-клиента к DaData и расширение CRM-модели.

Что меняется:
  * ``City.fias_id``, ``Street.fias_id``, ``House.fias_id`` → ``external_id``
    (нейтральное имя: тот же UUID приходит теперь от DaData).
  * Новые справочники: ``DealStatus``, ``TaskStatus``.
  * У сделки появляется FK на ``DealStatus`` и поле ``notes``.
  * Модель ``PropertyPhoto`` получает поля ``image`` (загрузка файла),
    ``caption`` и ``is_cover``.
  * Новая модель ``Task`` — задача сотрудника.
  * У ``User.user_type`` теперь есть значение по умолчанию ``client``
    (регистрация всегда создаёт клиента).
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('key', '0001_initial'),
    ]

    operations = [
        # --- адресная иерархия: fias_id → external_id -------------------
        migrations.RenameField(
            model_name='city',
            old_name='fias_id',
            new_name='external_id',
        ),
        migrations.RenameField(
            model_name='street',
            old_name='fias_id',
            new_name='external_id',
        ),
        migrations.RenameField(
            model_name='house',
            old_name='fias_id',
            new_name='external_id',
        ),
        migrations.AlterField(
            model_name='city',
            name='external_id',
            field=models.UUIDField(
                blank=True, db_index=True, null=True,
                help_text='Внешний идентификатор адресного реестра (из DaData)',
            ),
        ),

        # --- тип пользователя по умолчанию ------------------------------
        migrations.AlterField(
            model_name='user',
            name='user_type',
            field=models.CharField(
                choices=[('employee', 'Сотрудник'), ('client', 'Клиент')],
                default='client',
                max_length=20,
            ),
        ),

        # --- новые справочники ------------------------------------------
        migrations.CreateModel(
            name='DealStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=50)),
                ('order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Статус сделки',
                'verbose_name_plural': 'Статусы сделок',
                'db_table': 'deal_statuses',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='TaskStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=50)),
                ('order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Статус задачи',
                'verbose_name_plural': 'Статусы задач',
                'db_table': 'task_statuses',
                'ordering': ['order'],
            },
        ),

        # --- расширение сделки ------------------------------------------
        migrations.AddField(
            model_name='deal',
            name='status',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='deals',
                to='key.dealstatus',
            ),
        ),
        migrations.AddField(
            model_name='deal',
            name='notes',
            field=models.TextField(blank=True, null=True),
        ),

        # --- расширение фотографий объектов -----------------------------
        migrations.AddField(
            model_name='propertyphoto',
            name='image',
            field=models.ImageField(blank=True, null=True,
                                    upload_to='properties/%Y/%m/'),
        ),
        migrations.AddField(
            model_name='propertyphoto',
            name='caption',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='propertyphoto',
            name='is_cover',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='propertyphoto',
            name='url',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name='propertyphoto',
            options={
                'ordering': ['-is_cover', '-uploaded_at'],
                'verbose_name': 'Фото объекта',
                'verbose_name_plural': 'Фото объектов',
            },
        ),

        # --- задачи сотрудников -----------------------------------------
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('priority', models.CharField(
                    choices=[('low', 'Низкий'), ('normal', 'Обычный'), ('high', 'Высокий')],
                    default='normal', max_length=10)),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assignee', models.ForeignKey(
                    limit_choices_to={'user_type': 'employee'},
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='assigned_tasks',
                    to=settings.AUTH_USER_MODEL)),
                ('client', models.ForeignKey(
                    blank=True, null=True,
                    limit_choices_to={'user_type': 'client'},
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='client_tasks',
                    to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='created_tasks',
                    to=settings.AUTH_USER_MODEL)),
                ('deal', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tasks', to='key.deal')),
                ('property', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tasks', to='key.property')),
                ('request', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tasks', to='key.request')),
                ('status', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tasks', to='key.taskstatus')),
            ],
            options={
                'verbose_name': 'Задача',
                'verbose_name_plural': 'Задачи',
                'db_table': 'tasks',
                'ordering': ['-created_at'],
            },
        ),
    ]
