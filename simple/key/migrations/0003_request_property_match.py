"""
Миграция: привязка объектов недвижимости к заявкам клиентов.

Что делает:
    * добавляет поле ``Request.property`` (FK на ``Property``, nullable) —
      для «быстрой заявки» с карточки конкретного объекта;
    * делает поле ``Request.agent`` необязательным (клиент подаёт заявку
      до того, как сотрудник её взял в работу);
    * создаёт модель ``RequestPropertyMatch`` — подборку вариантов,
      которые агент предлагает клиенту по заявке на подбор.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('key', '0002_dealstatus_taskstatus_alter_propertyphoto_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='request',
            name='agent',
            field=models.ForeignKey(
                blank=True, null=True,
                limit_choices_to={'user_type': 'employee'},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='agent_requests',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='request',
            name='property',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='direct_requests',
                to='key.property',
            ),
        ),
        migrations.CreateModel(
            name='RequestPropertyMatch',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('agent_note', models.TextField(blank=True, null=True)),
                ('is_offered', models.BooleanField(
                    default=True,
                    help_text='Предложено клиенту')),
                ('is_rejected', models.BooleanField(
                    default=False,
                    help_text='Клиент отказался')),
                ('created_at', models.DateTimeField(
                    default=django.utils.timezone.now)),
                ('agent', models.ForeignKey(
                    limit_choices_to={'user_type': 'employee'},
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='proposed_matches',
                    to=settings.AUTH_USER_MODEL)),
                ('property', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='request_matches',
                    to='key.property')),
                ('request', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='matches',
                    to='key.request')),
            ],
            options={
                'verbose_name': 'Вариант по заявке',
                'verbose_name_plural': 'Варианты по заявкам',
                'db_table': 'request_property_matches',
                'ordering': ['-created_at'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('request', 'property'),
                        name='unique_request_property_match',
                    ),
                ],
            },
        ),
    ]
