import datetime
import json
import os
import re
from operator import itemgetter

import requests
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from django.utils import six
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, generics, status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.renderers import StaticHTMLRenderer
from rest_framework.response import Response

from tunga.settings import MEDIA_ROOT, MEDIA_URL
from tunga_auth.utils import get_session_visitor_email
from tunga_profiles.models import Skill
from tunga_projects.models import Project, ProgressEvent
from tunga_projects.serializers import SimpleProjectSerializer, SimpleProgressEventSerializer
from tunga_projects.utils import weekly_project_report, weekly_payment_report
from tunga_tasks.renderers import PDFRenderer
from tunga_utils.constants import EVENT_SOURCE_HUBSPOT
from tunga_utils.models import ContactRequest, InviteRequest, ExternalEvent, SearchEvent
from tunga_utils.notifications.slack import notify_new_calendly_event
from tunga_utils.serializers import SkillSerializer, ContactRequestSerializer, InviteRequestSerializer
from tunga_utils.tasks import log_calendly_event_hubspot


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Skills Resource
    """
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [AllowAny]
    search_fields = ('name', )


class ContactRequestView(generics.CreateAPIView):
    """
    Contact Request Resource
    """
    queryset = ContactRequest.objects.all()
    serializer_class = ContactRequestSerializer
    permission_classes = [AllowAny]


class InviteRequestView(generics.CreateAPIView):
    """
    Invite Request Resource
    """
    queryset = InviteRequest.objects.all()
    serializer_class = InviteRequestSerializer
    permission_classes = [AllowAny]


@api_view(http_method_names=['GET'])
@permission_classes([AllowAny])
def get_medium_posts(request):
    r = requests.get('https://medium.com/@tunga_io/latest?format=json')
    posts = []
    if r.status_code == 200:
        def get_image(post):
            base_url = 'https://miro.medium.com/max/1200/'

            # preview image
            if post['virtuals']['previewImage']:
                return base_url + post['virtuals']['previewImage']['imageId']

            # first image in preview content
            for item in post['previewContent']['bodyModel']['paragraphs']:
                if item['name'] == 'previewImage':
                    return base_url + item['metadata']['id']

            # first tag image
            for item in post['virtuals']['tags']:
                if item['metadata']['coverImage']['id']:
                    return base_url + item['metadata']['coverImage']['id']
            return ''

        try:
            response = json.loads(re.sub(r'^[^{]*\{', '{', r.text))
            posts = [
                dict(
                    id=post['id'],
                    slug=post['slug'],
                    url='https://blog.tunga.io/{}-{}'.format(post['slug'], post['id']),
                    title=post['title'],
                    subtitle=post['content']['subtitle'],
                    image=get_image(post),
                    created_at=post['createdAt'],
                    readingTime=post['virtuals']['readingTime'],
                    totalClapCount=post['virtuals']['totalClapCount'],
                    wordCount=post['virtuals']['wordCount'],
                    tags=[tag['name'] for tag in post['virtuals']['tags']],
                    latestVersion=post['latestVersion'],
                )
                for key, post in six.iteritems(response['payload']['references']['Post'])
                ]
            # Sort latest first
            posts = sorted(posts, key=itemgetter('created_at'), reverse=True)
        except:
            pass
    return Response(posts)


@api_view(http_method_names=['GET'])
@permission_classes([AllowAny])
def get_oembed_details(request):
    r = requests.get('https://noembed.com/embed?url=' + request.GET.get('url', None))
    oembed_response = dict()
    if r.status_code == 200:
        oembed_response = r.json()
    return Response(oembed_response)


@api_view(http_method_names=['POST'])
@permission_classes([IsAuthenticated])
def upload_file(request):
    file_response = dict()
    if request.FILES['file']:
        uploaded_file = request.FILES['file']
        store_path = datetime.datetime.utcnow().strftime('uploads/%Y/%m/%d')
        fs = FileSystemStorage(
            location=os.path.join(MEDIA_ROOT, store_path),
            base_url='{}{}/'.format(MEDIA_URL, store_path)
        )
        filename = fs.save(uploaded_file.name, uploaded_file)
        uploaded_file_url = fs.url(filename)
        file_response = dict(url=uploaded_file_url)
    return Response(file_response)


@api_view(http_method_names=['GET'])
@permission_classes([AllowAny])
def find_by_legacy_id(request, model, pk):
    response = None
    try:
        if model == 'task':
            project = Project.objects.get(legacy_id=pk)
            response = SimpleProjectSerializer(instance=project).data
        elif model == 'event':
            progress_event = ProgressEvent.objects.get(legacy_id=pk)
            response = SimpleProgressEventSerializer(instance=progress_event).data
    except ObjectDoesNotExist:
        pass
    if response:
        return Response(response)
    return Response(dict(message='{} #{} replacement found'.format(model, pk)), status=status.HTTP_404_NOT_FOUND)


@api_view(http_method_names=['GET'])
@permission_classes([IsAdminUser])
@renderer_classes([PDFRenderer, StaticHTMLRenderer])
def weekly_report(request, subject):
    if subject == 'payments':
        if request.accepted_renderer.format == 'html':
            return HttpResponse(weekly_payment_report(render_format='html'))
        else:
            http_response = HttpResponse(weekly_payment_report(render_format='pdf'), content_type='application/pdf')
            http_response['Content-Disposition'] = 'filename="weekly_project_report.pdf"'
            return http_response
    else:
        if request.accepted_renderer.format == 'html':
            return HttpResponse(weekly_project_report(render_format='html'))
        else:
            http_response = HttpResponse(weekly_project_report(render_format='pdf'), content_type='application/pdf')
            http_response['Content-Disposition'] = 'filename="weekly_project_report.pdf"'
            return http_response


@csrf_exempt
@api_view(http_method_names=['POST'])
@permission_classes([AllowAny])
def hubspot_notification(request):
    hs_signature = request.META.get('HTTP_X_HUBSPOT_SIGNATURE', None)

    payload = request.data
    if payload:
        ExternalEvent.objects.create(source=EVENT_SOURCE_HUBSPOT, payload=json.dumps(payload))
        return Response('Received')
    return Response('Failed to process', status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(http_method_names=['POST'])
@permission_classes([AllowAny])
def calendly_notification(request):
    payload = request.data
    if payload:
        event_type = payload.get('event', None)
        if event_type == 'invitee.created':
            data = payload.get('payload', None)

            if data:
                notify_new_calendly_event.delay(data)
                log_calendly_event_hubspot.delay(data)
        return Response('Received')
    return Response('Failed to process', status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(http_method_names=['POST'])
@permission_classes([AllowAny])
def search_logger(request):
    payload = request.data
    if payload and payload.get('search', None):
        user = None
        email = get_session_visitor_email(request)
        if request.user.is_authenticated:
            user = request.user
        SearchEvent.objects.create(
            user=user, email=email, query=payload.get('search', None),
            page=payload.get('page', 1) or 1
        )
        return Response('Logged')
    return Response('Failed to process', status=status.HTTP_400_BAD_REQUEST)
