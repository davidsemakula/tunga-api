# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-09 05:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0090_task_hubspot_deal_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='hubspot_deal_id',
            field=models.CharField(editable=False, max_length=12, null=True),
        ),
    ]
