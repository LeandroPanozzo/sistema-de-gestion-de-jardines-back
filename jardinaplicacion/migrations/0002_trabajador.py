# Generated by Django 5.2.1 on 2025-05-30 22:49

import django.contrib.auth.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('jardinaplicacion', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Trabajador',
            fields=[
            ],
            options={
                'verbose_name': 'Trabajador',
                'verbose_name_plural': 'Trabajadores',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('jardinaplicacion.customuser',),
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
