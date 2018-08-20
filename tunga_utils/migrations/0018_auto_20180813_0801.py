# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-08-13 08:01
from __future__ import unicode_literals

from django.db import migrations, models
import tunga_utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_utils', '0017_auto_20180813_0752'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inviterequest',
            name='cv',
            field=models.FileField(upload_to='cv/%Y/%m/%d', validators=[tunga_utils.validators.validate_file_size]),
        ),
    ]