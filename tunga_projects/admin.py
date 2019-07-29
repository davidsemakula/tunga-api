# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from tunga_projects.models import ProjectType, Project, ProjectMeta, ProgressEvent


@admin.register(ProjectType)
class ProjectType(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'deadline', 'created_at', 'archived')
    list_filter = ('archived',)
    search_fields = ('title',)


@admin.register(ProjectMeta)
class ProjectMetaAdmin(admin.ModelAdmin):
    list_display = ('project', 'meta_key', 'meta_value')
    list_filter = ('meta_key',)
    search_fields = ('meta_key', 'meta_value')


@admin.register(ProgressEvent)
class ProgressEventAdmin(admin.ModelAdmin):
    list_display = ('project', 'type', 'title', 'due_at', 'last_reminder_at')
    list_filter = ('type',)
    search_fields = ('title', 'project_title')
