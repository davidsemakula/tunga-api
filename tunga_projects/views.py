# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework.decorators import detail_route
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from tunga_projects.filterbackends import ProjectFilterBackend
from tunga_projects.filters import ProjectFilter, DocumentFilter, \
    ParticipationFilter, ProgressEventFilter, \
    ProgressReportFilter, InterestPollFilter, DeveloperRatingFilter
from tunga_projects.models import Project, Document, Participation, \
    ProgressEvent, ProgressReport, InterestPoll, DeveloperRating
from tunga_projects.serializers import ProjectSerializer, DocumentSerializer, \
    ParticipationSerializer, \
    ProgressEventSerializer, ProgressReportSerializer, InterestPollSerializer, \
    DeveloperRatingSerializer
from tunga_projects.tasks import manage_interest_polls
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class ProjectViewSet(ModelViewSet):
    """
    Project Resource
    """
    queryset = Project.objects.all(archived=False)
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ProjectFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ProjectFilterBackend,)
    search_fields = ('title',)

    @detail_route(
        methods=['post'], url_path='remind',
        permission_classes=[IsAuthenticated]
    )
    def remind(self, request, pk=None):
        """
        Remind Endpoint
        ---
        omit_serializer: True
        omit_parameters:
            - query
        """
        project = get_object_or_404(self.get_queryset(), pk=pk)
        manage_interest_polls.delay(project.id, remind=True)
        return Response({'message': 'reminders sent'})


class ParticipationViewSet(ModelViewSet):
    """
    Participation Resource
    """
    queryset = Participation.objects.all()
    serializer_class = ParticipationSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ParticipationFilter
    filter_backends = DEFAULT_FILTER_BACKENDS


class InterestPollViewSet(ModelViewSet):
    """
    Interest Poll Resource
    """
    queryset = InterestPoll.objects.all()
    serializer_class = InterestPollSerializer
    permission_classes = [AllowAny]
    filter_class = InterestPollFilter
    filter_backends = DEFAULT_FILTER_BACKENDS


class DocumentViewSet(ModelViewSet):
    """
    Document Resource
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = DocumentFilter
    filter_backends = DEFAULT_FILTER_BACKENDS


class ProgressEventViewSet(ModelViewSet):
    """
    Progress Event Resource
    """
    queryset = ProgressEvent.objects.all()
    serializer_class = ProgressEventSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ProgressEventFilter
    filter_backends = DEFAULT_FILTER_BACKENDS


class ProgressReportViewSet(ModelViewSet):
    """
    Progress Report Resource
    """
    queryset = ProgressReport.objects.all()
    serializer_class = ProgressReportSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ProgressReportFilter
    filter_backends = DEFAULT_FILTER_BACKENDS


class DeveloperRatingViewSet(ModelViewSet):
    """
    Developer Rating Resource
    """
    queryset = DeveloperRating.objects.all()
    serializer_class = DeveloperRatingSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = DeveloperRatingFilter
    filter_backends = DEFAULT_FILTER_BACKENDS
