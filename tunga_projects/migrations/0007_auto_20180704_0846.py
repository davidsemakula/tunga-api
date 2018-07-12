# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-07-04 08:46
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import tagulous.models.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tunga_projects', '0006_auto_20180623_0933'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgressEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.PositiveSmallIntegerField(choices=[(b'developer', b'Developer Update'), (b'pm', b'PM Report'), (b'client', b'Client Survey'), (b'milestone', b'Milestone'), (b'internal', b'Internal Milestone')], default=1, help_text='developer - Developer Update,pm - PM Report,client - Client Survey,milestone - Milestone,internal - Internal Milestone')),
                ('due_at', models.DateTimeField()),
                ('title', models.CharField(blank=True, max_length=200, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('last_reminder_at', models.DateTimeField(blank=True, null=True)),
                ('missed_notification_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='progress_events_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-due_at'],
            },
        ),
        migrations.AddField(
            model_name='project',
            name='start_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='skills',
            field=tagulous.models.fields.TagField(_set_tag_meta=True, blank=True, help_text='Enter a comma-separated tag string', initial='PHP, JavaScript, Python, Ruby, Java, C#, C++, Ruby, Swift, Objective C, .NET, ASP.NET, Node.js,HTML, CSS, HTML5, CSS3, XML, JSON, YAML,Django, Ruby on Rails, Flask, Yii, Lavarel, Express.js, Spring, JAX-RS,AngularJS, React.js, Meteor.js, Ember.js, Backbone.js,WordPress, Joomla, Drupal,jQuery, jQuery UI, Bootstrap, AJAX,Android, iOS, Windows Mobile, Apache Cordova, Ionic,SQL, MySQL, PostgreSQL, MongoDB, CouchDB,Git, Subversion, Mercurial, Docker, Ansible, Webpack, Grunt, Gulp, Ant, Maven, Gradle', space_delimiter=False, to='tunga_profiles.Skill'),
        ),
        migrations.AddField(
            model_name='progressevent',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tunga_projects.Project'),
        ),
        migrations.AlterUniqueTogether(
            name='progressevent',
            unique_together=set([('project', 'type', 'due_at')]),
        ),
    ]
