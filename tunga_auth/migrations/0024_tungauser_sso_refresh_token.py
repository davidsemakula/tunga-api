# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-11-24 07:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_auth', '0023_tungauser_sso_uuid'),
    ]

    operations = [
        migrations.AddField(
            model_name='tungauser',
            name='sso_refresh_token',
            field=models.TextField(blank=True, null=True),
        ),
    ]