# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-11-15 13:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_tasks', '0139_auto_20171115_0920'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participantpayment',
            name='status',
            field=models.CharField(choices=[(b'pending', 'Pending'), (b'initiated', 'Initiated'), (b'processing', 'Processing'), (b'completed', 'Completed'), (b'failed', 'Failed'), (b'canceled', 'Canceled'), (b'retry', 'Retry')], default=b'pending', help_text='pending - Pending, initiated - Initiated, processing - Processing, completed - Completed, failed - Failed, canceled - Canceled, retry - Retry', max_length=30),
        ),
    ]
