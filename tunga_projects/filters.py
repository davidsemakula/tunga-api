import datetime

import django_filters
from dateutil.relativedelta import relativedelta
from django.db.models import Q

from tunga_projects.models import Project, Document, Participation, \
    ProgressEvent, ProgressReport, InterestPoll, DeveloperRating
from tunga_utils.filters import GenericDateFilterSet


class ProjectFilter(GenericDateFilterSet):
    participant = django_filters.NumberFilter(name='participants__user', label='Participant')
    skill = django_filters.CharFilter(name='skills__name', label='skills')
    skill_id = django_filters.NumberFilter(name='skills', label='skills (by ID)')
    owner = django_filters.CharFilter(method='filter_owner')

    class Meta:
        model = Project
        fields = (
            'user', 'type', 'category', 'expected_duration', 'stage', 'participant', 'skill', 'skill_id', 'archived'
        )

    def filter_owner(self, queryset, name, value):
        return queryset.filter(Q(owner=value) | Q(user=value))


class ParticipationFilter(GenericDateFilterSet):
    class Meta:
        model = Participation
        fields = (
            'project', 'created_by'
        )


class InterestPollFilter(GenericDateFilterSet):
    class Meta:
        model = InterestPoll
        fields = (
            'project', 'created_by'
        )


class DocumentFilter(GenericDateFilterSet):
    class Meta:
        model = Document
        fields = (
            'project', 'created_by'
        )


class ProgressEventFilter(GenericDateFilterSet):
    types = django_filters.CharFilter(method='filter_multi_types')
    users = django_filters.CharFilter(method='filter_multi_users')
    overdue = django_filters.BooleanFilter(method='filter_overdue')

    class Meta:
        model = ProgressEvent
        fields = (
            'project', 'created_by', 'type', 'types', 'users', 'created_at', 'overdue'
        )

    def filter_multi_types(self, queryset, name, value):
        value = value.split(",")
        return queryset.filter(Q(type__in=value))

    def filter_multi_users(self, queryset, name, value):
        value = value.split(",")
        return queryset.filter(user_id__in=value)

    def filter_overdue(self, queryset, name, value):
        if value:
            right_now = datetime.datetime.utcnow()
            past_by_18_hours = right_now - relativedelta(hours=18)
            past_by_48_hours = right_now - relativedelta(hours=48)
            return queryset.filter(due_at__range=[past_by_48_hours, past_by_18_hours])
        return queryset


class ProgressReportFilter(GenericDateFilterSet):
    project = django_filters.NumberFilter(name='event__project')
    type = django_filters.NumberFilter(name='event__type')

    class Meta:
        model = ProgressReport
        fields = (
            'event', 'user', 'project', 'type'
        )


class DeveloperRatingFilter(GenericDateFilterSet):
    project = django_filters.NumberFilter(name='event__project')
    type = django_filters.NumberFilter(name='event__type')

    class Meta:
        model = DeveloperRating
        fields = (
            'event', 'user', 'project', 'type'
        )
