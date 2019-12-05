# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import re
import uuid

import tagulous.models
from actstream.models import Action
from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum
from django.utils.encoding import python_2_unicode_compatible
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga.settings import TUNGA_URL
from tunga_profiles.models import Skill
from tunga_utils.constants import PROJECT_TYPE_CHOICES, PROJECT_TYPE_OTHER, \
    CURRENCY_EUR, \
    PROJECT_EXPECTED_DURATION_CHOICES, CURRENCY_CHOICES_EUR_ONLY, \
    STATUS_INITIAL, REQUEST_STATUS_CHOICES, \
    STATUS_ACCEPTED, PROJECT_DOCUMENT_CHOICES, DOC_OTHER, \
    PROGRESS_EVENT_DEVELOPER, PROGRESS_EVENT_TYPE_CHOICES, \
    PROGRESS_REPORT_STATUS_CHOICES, PROGRESS_REPORT_STUCK_REASON_CHOICES, \
    PROGRESS_EVENT_PM, PROGRESS_EVENT_MILESTONE, \
    PROGRESS_EVENT_CLIENT, PROGRESS_EVENT_INTERNAL, PROJECT_STAGE_ACTIVE, \
    PROJECT_STAGE_CHOICES, STATUS_UNINTERESTED, \
    STATUS_INTERESTED, INVOICE_TYPE_SALE, INVOICE_TYPE_PURCHASE, \
    PROJECT_CATEGORY_CHOICES
from tunga_utils.models import Rating


@python_2_unicode_compatible
class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             related_name='projects_created',
                             on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.TextField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='projects_owned',
        on_delete=models.DO_NOTHING, blank=True, null=True
    )
    pm = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='projects_managed',
        on_delete=models.DO_NOTHING, blank=True, null=True
    )
    skills = tagulous.models.TagField(Skill, blank=True)
    budget = models.DecimalField(
        max_digits=17, decimal_places=2, blank=True, null=True, default=None
    )
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES_EUR_ONLY,
                                default=CURRENCY_EUR)
    type = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES,
                            default=PROJECT_TYPE_OTHER)
    category = models.CharField(max_length=20, choices=PROJECT_CATEGORY_CHOICES,
                                blank=True, null=True)
    expected_duration = models.CharField(max_length=20,
                                         choices=PROJECT_EXPECTED_DURATION_CHOICES,
                                         blank=True,
                                         null=True)
    stage = models.CharField(max_length=20, choices=PROJECT_STAGE_CHOICES,
                             default=PROJECT_STAGE_ACTIVE)

    # State identifiers
    client_survey_enabled = models.BooleanField(default=True)
    pm_updates_enabled = models.BooleanField(default=True)
    closed = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)

    # Significant event dates
    start_date = models.DateTimeField(blank=True, null=True)
    deadline = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='Participation',
        through_fields=('project', 'user'),
        related_name='project_participants', blank=True)

    legacy_id = models.PositiveIntegerField(blank=True, null=True)
    migrated_at = models.DateTimeField(blank=True, null=True)
    hubspot_deal_id = models.CharField(editable=False, null=True, max_length=12)

    activity_objects = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='projects'
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']

    @allow_staff_or_superuser
    def is_participant(self, user, active=True):
        if user == self.user or user == self.owner:
            return True
        elif user.is_project_manager and self.pm == user:
            return True
        elif user.is_developer and self.participation_set.filter(
            user=user,
            status__in=active and [STATUS_ACCEPTED] or [STATUS_ACCEPTED,
                                                        STATUS_INITIAL]
        ).count() > 0:
            return True
        else:
            return False

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user or request.user == self.owner or request.user == self.pm

    @property
    def margin(self):
        from tunga_payments.models import Invoice
        sales_amount = Invoice.objects.filter(project=self,
                                              type=INVOICE_TYPE_SALE).aggregate(
            Sum('amount'))
        project_amount = Invoice.objects.filter(project=self,
                                                type=INVOICE_TYPE_PURCHASE).aggregate(
            Sum('amount'))
        sales_amount = sales_amount['amount__sum'] or 0
        project_amount = project_amount['amount__sum'] or 0
        return sales_amount - project_amount


@python_2_unicode_compatible
class Participation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             related_name='project_participation',
                             on_delete=models.DO_NOTHING)
    status = models.CharField(
        max_length=20, choices=REQUEST_STATUS_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in
                            REQUEST_STATUS_CHOICES]),
        default=STATUS_INITIAL
    )
    updates_enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   related_name='project_participants_added')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    legacy_id = models.PositiveIntegerField(blank=True, null=True)
    migrated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '#{} | {} - {}'.format(self.id,
                                      self.user.get_short_name() or self.user.username,
                                      self.project.title)

    class Meta:
        unique_together = ('user', 'project')
        ordering = ['-created_at']
        verbose_name_plural = 'participation'

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if self.status != STATUS_INITIAL and self.responded_at is None:
            self.responded_at = datetime.datetime.utcnow()
        super(Participation, self).save(force_insert=force_insert,
                                        force_update=force_update, using=using)

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.project.is_participant(request.user, active=False)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        allowed_users = [self.created_by, self.user, self.project.user]
        for user in [self.project.owner, self.project.pm]:
            if user:
                allowed_users.append(user)
        return request.user in allowed_users


@python_2_unicode_compatible
class InterestPoll(models.Model):
    status_choices = (
        (STATUS_INITIAL, 'Initial'),
        (STATUS_INTERESTED, 'Interested'),
        (STATUS_UNINTERESTED, 'Uninterested')
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             related_name='project_interest_polls',
                             on_delete=models.DO_NOTHING)
    status = models.CharField(
        max_length=20, choices=status_choices,
        help_text=','.join(
            ['%s - %s' % (item[0], item[1]) for item in status_choices]),
        default=STATUS_INITIAL
    )
    approval_status = models.CharField(
        max_length=20, choices=REQUEST_STATUS_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in
                            REQUEST_STATUS_CHOICES]),
        default=STATUS_INITIAL
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   related_name='project_interest_polls_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    reminded_at = models.DateTimeField(blank=True, null=True)
    token = models.UUIDField(default=uuid.uuid4)

    def __str__(self):
        return '#{} | {} - {}'.format(self.id,
                                      self.user.get_short_name() or self.user.username,
                                      self.project.title)

    class Meta:
        unique_together = ('user', 'project')
        ordering = ['-created_at']
        verbose_name = 'interest poll'
        verbose_name_plural = 'interest polls'

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if self.status != STATUS_INITIAL and self.responded_at is None:
            self.responded_at = datetime.datetime.utcnow()
        super(InterestPoll, self).save(force_insert=force_insert,
                                       force_update=force_update, using=using)

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.project.is_participant(request.user, active=False)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        allowed_users = [self.created_by, self.user, self.project.user]
        for user in [self.project.owner, self.project.pm]:
            if user:
                allowed_users.append(user)
        return request.user in allowed_users


@python_2_unicode_compatible
class Document(models.Model):
    project = models.ForeignKey(Project)
    type = models.CharField(choices=PROJECT_DOCUMENT_CHOICES, max_length=30,
                            default=DOC_OTHER)
    url = models.URLField(blank=True, null=True)
    file = models.FileField(verbose_name='Upload',
                            upload_to='documents/%Y/%m/%d', blank=True,
                            null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    legacy_id = models.PositiveIntegerField(blank=True, null=True)
    migrated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '{} | {}'.format(self.type, self.project)

    class Meta:
        ordering = ['-created_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.project.is_participant(request.user)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_manager or request.user.is_project_owner

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.created_by

    @property
    def download_url(self):
        if self.file:
            return '{}{}'.format(
                not re.match(r'://', self.file.url) and TUNGA_URL or '',
                self.file.url)
        elif self.url:
            return self.url
        return None


@python_2_unicode_compatible
class ProgressEvent(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    type = models.CharField(
        max_length=50,
        choices=PROGRESS_EVENT_TYPE_CHOICES, default=PROGRESS_EVENT_DEVELOPER,
        help_text=','.join(['{} - {}'.format(item[0], item[1]) for item in
                            PROGRESS_EVENT_TYPE_CHOICES])
    )
    due_at = models.DateTimeField()
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    last_reminder_at = models.DateTimeField(blank=True, null=True)
    missed_notification_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='progress_events_created',
        blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    legacy_id = models.PositiveIntegerField(blank=True, null=True)
    migrated_at = models.DateTimeField(blank=True, null=True)

    activity_objects = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='progress_events'
    )

    def __str__(self):
        return '{} | {} - {}'.format(self.type, self.title, self.due_at)

    class Meta:
        unique_together = ('project', 'type', 'due_at')
        ordering = ['-due_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.project.is_participant(request.user)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_owner or request.user.is_project_manager or request.user.is_project_owner

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.project.user or request.user == self.project.owner

    @property
    def participants(self):
        participants = []
        if self.type in [PROGRESS_EVENT_CLIENT, PROGRESS_EVENT_MILESTONE]:
            if self.project.owner:
                participants.append(self.project.owner)
            else:
                participants.append(self.project.user)
        if self.type in [PROGRESS_EVENT_PM, PROGRESS_EVENT_MILESTONE,
                         PROGRESS_EVENT_INTERNAL] and self.project.pm:
            participants.append(self.project.pm)
        if self.type in [PROGRESS_EVENT_DEVELOPER, PROGRESS_EVENT_MILESTONE]:
            participants.extend([
                participant.user
                for participant in
                self.project.participation_set.filter(status=STATUS_ACCEPTED,
                                                      updates_enabled=True)
            ])
        return participants

    @property
    def status(self):
        if self.progressreport_set.count() > 0:
            return 'completed'
        past_by_24_hours = datetime.datetime.utcnow() - relativedelta(hours=24)
        if self.due_at > past_by_24_hours:
            return 'upcoming'
        return 'missed'


@python_2_unicode_compatible
class ProgressReport(models.Model):
    event = models.ForeignKey(ProgressEvent, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.DO_NOTHING)

    # Status details
    status = models.CharField(
        max_length=50,
        choices=PROGRESS_REPORT_STATUS_CHOICES,
        help_text=','.join(
            ['%s - %s' % (item[0], item[1]) for item in
             PROGRESS_REPORT_STATUS_CHOICES]),
        blank=True, null=True
    )
    percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)], blank=True,
        null=True
    )
    accomplished = models.TextField(blank=True, null=True)
    todo = models.TextField(blank=True, null=True)
    obstacles = models.TextField(blank=True, null=True)
    obstacles_prevention = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    stuck_reason = models.CharField(
        max_length=50,
        choices=PROGRESS_REPORT_STUCK_REASON_CHOICES,
        help_text=','.join(
            ['%s - %s' % (item[0], item[1]) for item in
             PROGRESS_REPORT_STUCK_REASON_CHOICES]),
        blank=True, null=True
    )
    stuck_details = models.TextField(blank=True, null=True)

    # Deliverables
    rate_deliverables = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True,
        null=True
    )

    # Deadline Info
    started_at = models.DateTimeField(blank=True, null=True)
    last_deadline_met = models.NullBooleanField(blank=True, null=True)
    deadline_miss_communicated = models.NullBooleanField(blank=True, null=True)
    deadline_report = models.TextField(blank=True, null=True)
    next_deadline = models.DateTimeField(blank=True, null=True)
    next_deadline_meet = models.NullBooleanField(blank=True, null=True)
    next_deadline_fail_reason = models.TextField(blank=True, null=True)

    # PMs only
    team_appraisal = models.TextField(blank=True, null=True)

    # Clients only
    deliverable_satisfaction = models.NullBooleanField(blank=True, null=True)
    rate_communication = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True,
        null=True
    )
    pm_communication = models.NullBooleanField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    legacy_id = models.PositiveIntegerField(blank=True, null=True)
    migrated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '{0} - {1}%'.format(self.event, self.percentage)

    class Meta:
        ordering = ['-created_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.event.project.is_participant(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_developer or request.user.is_project_manager or request.user.is_project_owner

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


@python_2_unicode_compatible
class ProjectMeta(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    meta_key = models.CharField(max_length=30)
    meta_value = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='project_meta_created',
        blank=True, null=True,
        on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{} | {} - {}'.format(self.project, self.meta_key,
                                     self.meta_value)

    class Meta:
        ordering = ['created_at']
        unique_together = ('project', 'meta_key')


@python_2_unicode_compatible
class DeveloperRating(models.Model):
    event = models.ForeignKey(ProgressEvent, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.DO_NOTHING)

    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{} - {} | {} %'.format(self.event, self.user, self.rating)
