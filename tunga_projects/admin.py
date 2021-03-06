# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from tunga_projects.models import Project, ProjectMeta, ProgressEvent, \
    DeveloperRating, ProgressReport, Participation, InterestPoll


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'deadline', 'created_at', 'archived')
    list_filter = ('archived',)
    search_fields = ('title',)


@admin.register(Participation)
class ProjectParticipationAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'user', 'status', 'created_at',
                    'day_selection_for_updates')
    list_filter = ('status',)


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


@admin.register(InterestPoll)
class InterestPollAdmin(admin.ModelAdmin):
    list_display = ('project', 'id', 'status', 'approval_status', 'created_at')
    list_filter = ('status', 'approval_status')
    search_fields = ('project', 'user', 'status')


@admin.register(DeveloperRating)
class DevelopRatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'rating', 'created_by')
    list_filter = ('event',)
    search_fields = ('user',)


@admin.register(ProgressReport)
class ProgressReportAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'status',)
    list_filter = ('event',)
    search_fields = ('user',)
