# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-08-29 16:52
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tunga_utils', '0019_auto_20180814_0103'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeveloperRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='developer_request_client', to=settings.AUTH_USER_MODEL)),
                ('developer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='developer_request_developer', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
