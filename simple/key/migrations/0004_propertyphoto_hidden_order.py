"""
Переход с ``properties/%Y/%m/`` на ``%Y/%m/`` и расширение набора полей
``PropertyPhoto`` для ручного управления альбомом:

* ``is_hidden`` — мягкое скрытие фото (исключить из выдачи клиенту);
* ``order``    — ручной порядок фото внутри альбома;
* новая ``upload_to`` и порядок ``ordering`` в Meta.

Миграция НЕ перемещает уже загруженные файлы — записи ``PropertyPhoto``,
созданные до перехода, продолжат указывать на путь
``properties/YYYY/MM/...``. Это штатно: поле ``image`` хранит абсолютный
относительный путь, а не шаблон.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('key', '0003_request_property_match'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertyphoto',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='propertyphoto',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='propertyphoto',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='%Y/%m/'),
        ),
        migrations.AlterModelOptions(
            name='propertyphoto',
            options={
                'db_table': 'property_photos',
                'ordering': ['-is_cover', 'order', '-uploaded_at'],
                'verbose_name': 'Фото объекта',
                'verbose_name_plural': 'Фото объектов',
            },
        ),
    ]
