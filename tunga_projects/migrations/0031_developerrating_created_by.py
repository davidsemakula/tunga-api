# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-01-06 15:49
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tunga_projects', '0030_auto_20191206_1319'),
    ]

    operations = [
        migrations.AddField(
            model_name='developerrating',
            name='created_by',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, related_name='created_by', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
