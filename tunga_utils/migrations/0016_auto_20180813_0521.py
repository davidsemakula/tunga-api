# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-08-13 05:21
from __future__ import unicode_literals

from django.db import migrations, models
import django_countries.fields
import tunga_utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tunga_utils', '0015_auto_20180714_0404'),
    ]

    operations = [
        migrations.CreateModel(
            name='InviteRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('email', models.EmailField(max_length=254, unique=True, validators=[tunga_utils.validators.validate_email])),
                ('motivation', models.TextField()),
                ('country', django_countries.fields.CountryField(max_length=2)),
                ('cv', models.ImageField(blank=True, null=True, upload_to='cv/%Y/%m/%d', validators=[tunga_utils.validators.validate_file_size])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterModelOptions(
            name='sitemeta',
            options={'ordering': ['meta_key']},
        ),
    ]