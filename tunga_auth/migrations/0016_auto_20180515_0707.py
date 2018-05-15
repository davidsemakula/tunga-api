# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-05-15 07:07
from __future__ import unicode_literals

from django.db import migrations, models
import tunga_utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_auth', '0015_tungauser_is_internal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tungauser',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='photos/%Y/%m/%d', validators=[tunga_utils.validators.validate_file_size]),
        ),
    ]