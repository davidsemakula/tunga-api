# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-23 00:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0095_task_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='survey_client',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
    ]