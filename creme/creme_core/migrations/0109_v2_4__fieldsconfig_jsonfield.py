# Generated by Django 3.2.12 on 2022-05-12 13:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('creme_core', '0108_v2_4__bricks_jsonfields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fieldsconfig',
            name='raw_descriptions',
            field=models.JSONField(default=list, editable=False),
        ),
    ]
