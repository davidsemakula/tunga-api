import datetime
import json
import os
import re
from operator import itemgetter
from urlparse import urlparse

from django.template.defaultfilters import truncatewords
from django.utils.html import strip_tags
from lxml import etree, html
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
from tunga_profiles.filters import SkillFilter
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
    filter_class = SkillFilter
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
    r = requests.get('https://medium.com/feed/@tunga_io')
    posts = []
    if r.status_code == 200:
        try:
            tree = etree.fromstring(
                r.text.encode('utf-8')
                    .replace('content:encoded', 'contentEncoded')
                    .replace('dc:creator', 'dcCreator')
                    .replace('atom:updated', 'atomUpdated')
            )

            for item in tree.xpath('/rss/channel/item'):
                story = dict()
                story['guid'] = item.xpath('./guid/text()')
                story['url'] = item.xpath('./link/text()')
                story['title'] = item.xpath('./title/text()')
                story['tags'] = item.xpath('./category/text()')
                story['content'] = item.xpath(
                    './contentEncoded/text()')  # content:encoded
                story['creator'] = item.xpath(
                    './dcCreator/text()')  # dc:creator
                story['published_at'] = item.xpath('./pubDate/text()')
                story['updated_at'] = item.xpath(
                    './atomUpdated/text()')  # atom:updated

                for key in story:
                    if story[key] and type(
                        story[key]) == list and key != 'tags':
                        story[key] = story[key][0]

                story['created_at'] = story['published_at']
                if story['content']:
                    content_tree = html.fromstring(
                        '<div>' + story['content'] + '</div>'
                    )
                    image = content_tree.xpath('.//figure/img/@src')

                    if image and type(image) == list:
                        story['image'] = image[0]
                    else:
                        story['image'] = image or ''
                    story['images'] = image

                    paragraphs = content_tree.xpath('.//p/text()')
                    if paragraphs and type(image) == list:
                        story['intro'] = paragraphs[0]
                    else:
                        story['intro'] = paragraphs or ''

                    story['intro'] = strip_tags(story['intro']).strip()
                    story['excerpt'] = truncatewords(story['intro'], 30)
                    # For backwards compatibility
                    story['subtitle'] = story['excerpt']
                else:
                    story['image'] = ''
                    story['intro'] = ''
                    story['subtitle'] = ''

                story_id = ''
                if story['guid']:
                    story_id = story['guid'].replace('https://medium.com/p/',
                                                     '')
                story['id'] = story_id

                slug = ''
                if story['id'] and story['url']:
                    path = urlparse(story['url']).path
                    if path:
                        slug = path.replace('/', '').replace(
                            '-{}'.format(story['id']), '')
                story['slug'] = slug

                posts.append(story)
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
