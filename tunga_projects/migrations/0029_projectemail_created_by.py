# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-04-16 13:54
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tunga_projects', '0028_projectemail'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectemail',
            name='created_by',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
