# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2018-02-27 14:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0161_taskinvoice_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='taskinvoice',
            name='version',
            field=models.FloatField(blank=True, default=2.0, null=True),
        ),
    ]
