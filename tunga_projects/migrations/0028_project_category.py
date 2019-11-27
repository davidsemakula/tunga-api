# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-10-18 11:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_projects', '0027_interestpoll_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='category',
            field=models.CharField(blank=True, choices=[(b'project', b'Project'), (b'dedicated', b'Dedicated'), (b'other', b'Other'), (None, b'None')], max_length=20, null=True),
        ),
    ]