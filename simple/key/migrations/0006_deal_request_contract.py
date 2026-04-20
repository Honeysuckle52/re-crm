"""
Добавляет к модели :class:`key.models.Deal`:

* связь ``request`` (OneToOne → ``Request``) — чтобы сделка, созданная
  автоматически при закрытии заявки, ссылалась на исходную заявку и
  нельзя было создать дубль;
* поля ``contract_file`` (PDF-договор) и ``contract_generated_at``
  (момент генерации).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('key', '0005_task_fields_outgoing_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='deal',
            name='request',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='deal',
                to='key.request',
            ),
        ),
        migrations.AddField(
            model_name='deal',
            name='contract_file',
            field=models.FileField(
                blank=True, null=True, upload_to='contracts/%Y/%m/',
            ),
        ),
        migrations.AddField(
            model_name='deal',
            name='contract_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
