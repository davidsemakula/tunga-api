# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-12-06 13:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_projects', '0029_auto_20191205_1203'),
    ]

    operations = [
        migrations.AddField(
            model_name='participation',
            name='day_selection_for_updates',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='participation',
            name='update_days',
            field=models.CharField(blank=True, default=b'0,1,2,3,4', max_length=55, null=True),
        ),
    ]