# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-12-21 08:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_projects', '0034_developerrating_reason_of_rating'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='expected_duration',
            field=models.CharField(blank=True, choices=[(b'4w', b'2-4 Weeks'), (b'3m', b'1-3 Months'), (b'6m', b'3-6 Months'), (b'12m', b'6-12 Months'), (b'permanent', b'Permanent')], max_length=20, null=True),
        ),
    ]
