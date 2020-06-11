# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms
from django.shortcuts import render, redirect
from django.views.generic import CreateView, TemplateView, FormView
from dry_rest_permissions.generics import DRYObjectPermissions, DRYPermissions
from rest_framework import status
from rest_framework.decorators import detail_route, list_route
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from tunga_auth.models import TungaUser
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
from tunga_utils.constants import PROJECT_STAGE_OPPORTUNITY, \
    PROJECT_STAGE_ACTIVE, STATUS_ACCEPTED
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class ProjectViewSet(ModelViewSet):
    """
    Project Resource
    """
    queryset = Project.objects.all()
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

    @list_route(
        methods=['get'], url_path='archived',
        permission_classes=[IsAuthenticated, DRYPermissions],
        filter_backends=DEFAULT_FILTER_BACKENDS + (ProjectFilterBackend,),
        serializer_class=ProjectSerializer,
    )
    def archived(self, request):
        results = Project.objects.filter(archived=True,
                                         stage=PROJECT_STAGE_ACTIVE)
        output_serializer = ProjectSerializer(results, many=True)
        data = output_serializer.data[:]
        page = self.paginate_queryset(results)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(data, status=status.HTTP_201_CREATED)

    @list_route(
        methods=['get'], url_path='opportunities',
        permission_classes=[IsAuthenticated, DRYPermissions],
        filter_backends=DEFAULT_FILTER_BACKENDS + (ProjectFilterBackend,),
        serializer_class=ProjectSerializer,
    )
    def opportunities(self, request):
        results = Project.objects.filter(archived=False,
                                         stage=PROJECT_STAGE_OPPORTUNITY)
        output_serializer = ProjectSerializer(results, many=True)
        data = output_serializer.data[:]
        page = self.paginate_queryset(results)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(data, status=status.HTTP_201_CREATED)


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


class GeeksForm(forms.Form):
    # specify fields for model
    title = forms.CharField()
    description = forms.CharField(widget=forms.Textarea)


class ClientSurveySuccessTemplate(TemplateView):
    template_name = "tunga/html/success_submission.html"


class ClientSurveyErrorTemplate(TemplateView):
    template_name = "tunga/html/error_submission.html"


class ClientSurveyTemplate(TemplateView):
    template_name = "tunga/html/survey_confirmation.html"

    def get_context_data(self, **kwargs):
        project_id = kwargs.get('id', None)
        project = Project.objects.filter(id=project_id).first()
        team_users_ids = Participation.objects.filter(project=project,
                                                      status=STATUS_ACCEPTED).values_list(
            'user_id', flat=True)
        team_users_ids = list(team_users_ids)
        developers = TungaUser.objects.filter(id__in=team_users_ids)
        project_event = ProgressEvent.objects.filter(project=project).first()
        context = super(ClientSurveyTemplate, self).get_context_data(**kwargs)
        context['project'] = project
        context['project_event'] = project_event
        context['developers'] = developers
        return context


class ClientSurveyFormView(CreateView):
    template_name = "tunga/html/survey_confirmation.html"
    model = DeveloperRating

    def post(self, request, *args, **kwargs):
        print(request)
        print(request.POST)
        event_id = request.POST['event']
        rating_type = request.POST['rating_type']
        progress_event = ProgressEvent.objects.filter(id=event_id).first()
        project = progress_event.project
        team_users_ids = Participation.objects.filter(project=project,
                                                      status=STATUS_ACCEPTED).values_list(
            'user_id', flat=True)
        team_users_ids = list(team_users_ids)
        if rating_type == 'project':
            project_rating = request.POST.get("project-rating-%s" % project.id,
                                              None)
            if project_rating:
                progress_report = ProgressReport.objects.create(
                    rate_deliverables=project_rating,
                    user=project.owner,
                    event_id=event_id)
            return redirect('client_survey_success', )

        elif rating_type == 'dedicated':
            for user_id in team_users_ids:
                rating = request.POST.get(str(int(user_id)), None)
                owner = project.owner or project.pm
                if rating:
                    developer_rating = DeveloperRating.objects.create(
                        user_id=user_id,
                        rating=int(rating),
                        created_by=owner,
                        event_id=event_id)
            return redirect('client_survey_success')
        return super(ClientSurveyFormView, self).post(request, *args, **kwargs)
