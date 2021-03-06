# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-12-21 08:22
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import tunga_utils.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tunga_profiles', '0044_developerinvitation_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfileProject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_month', models.PositiveSmallIntegerField(choices=[(1, b'Jan'), (2, b'Feb'), (3, b'Mar'), (4, b'Apr'), (5, b'May'), (6, b'Jun'), (7, b'Jul'), (8, b'Aug'), (9, b'Sep'), (10, b'Oct'), (11, b'Nov'), (12, b'Dec')])),
                ('start_year', models.PositiveIntegerField(validators=[tunga_utils.validators.validate_year])),
                ('end_month', models.PositiveSmallIntegerField(blank=True, choices=[(1, b'Jan'), (2, b'Feb'), (3, b'Mar'), (4, b'Apr'), (5, b'May'), (6, b'Jun'), (7, b'Jul'), (8, b'Aug'), (9, b'Sep'), (10, b'Oct'), (11, b'Nov'), (12, b'Dec')], null=True)),
                ('end_year', models.PositiveIntegerField(blank=True, null=True, validators=[tunga_utils.validators.validate_year])),
                ('details', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('title', models.CharField(max_length=500)),
                ('category', models.CharField(choices=[(b'tunga_project', b'Tunga Project'), (b'other', b'Other')], max_length=50)),
                ('project_link', models.CharField(blank=True, max_length=255, null=True)),
                ('repository_link', models.CharField(blank=True, max_length=255, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'project',
            },
        ),
    ]
