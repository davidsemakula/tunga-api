# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-10-31 09:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_auth', '0010_auto_20170319_1543'),
    ]

    operations = [
        migrations.AddField(
            model_name='tungauser',
            name='agree_version',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='tungauser',
            name='agreed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
