import datetime
import json
import re
from six.moves.urllib_parse import urlencode, quote_plus

import requests
from allauth.socialaccount.providers.facebook.provider import FacebookProvider
from allauth.socialaccount.providers.github.provider import GitHubProvider
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.slack.provider import SlackProvider
from django.contrib.auth import get_user_model, logout
from django.contrib.sitemaps import Sitemap
from django.core.urlresolvers import reverse
from django.http.response import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from dry_rest_permissions.generics import DRYPermissions
from rest_framework import views, status, generics, viewsets, mixins
from rest_framework.decorators import detail_route, permission_classes, \
    api_view, list_route, renderer_classes
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.renderers import StaticHTMLRenderer, TemplateHTMLRenderer, \
    JSONRenderer
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR, HTTP_401_UNAUTHORIZED
from slacker import Slacker
from weasyprint import HTML

from tunga import settings
from tunga.settings import GITHUB_SCOPES, COINBASE_CLIENT_ID, COINBASE_CLIENT_SECRET, SOCIAL_CONNECT_ACTION, \
    SOCIAL_CONNECT_NEXT, SOCIAL_CONNECT_USER_TYPE, SOCIAL_CONNECT_ACTION_REGISTER, \
    SOCIAL_CONNECT_ACTION_CONNECT, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SOCIAL_CONNECT_TASK, SOCIAL_CONNECT_CALLBACK, \
    SOCIAL_CONNECT_PROJECT, TUNGA_URL
from tunga_auth.filterbackends import UserFilterBackend
from tunga_auth.filters import UserFilter
from tunga_auth.models import EmailVisitor, TungaUser
from tunga_auth.serializers import UserSerializer, AccountInfoSerializer, EmailVisitorSerializer
from tunga_auth.utils import get_session_task, get_session_visitor_email, create_email_visitor_session, \
    get_session_next_url, get_session_project
from tunga_profiles.models import BTCWallet, UserProfile, AppIntegration, UserRequest
from tunga_projects.utils import save_project_metadata
from tunga_tasks.renderers import PDFRenderer
from tunga_tasks.utils import save_task_integration_meta
from tunga_utils import coinbase_utils, slack_utils, exact_utils, payoneer_utils
from tunga_utils.constants import BTC_WALLET_PROVIDER_COINBASE, PAYMENT_METHOD_BTC_WALLET, USER_TYPE_DEVELOPER, \
    USER_TYPE_PROJECT_OWNER, APP_INTEGRATION_PROVIDER_SLACK, APP_INTEGRATION_PROVIDER_HARVEST, STATUS_APPROVED, \
    STATUS_DECLINED, STATUS_PENDING, STATUS_INITIATED
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_utils.helpers import get_social_token
from tunga_utils.serializers import SimpleUserSerializer


class VerifyUserView(views.APIView):
    """
    Verifies Current user.
    Returns user object if user is logged in, otherwise 401 Unauthorized
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, request):
        user = request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None

    def get(self, request):
        user = self.get_object(request)
        if user is None:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not logged in'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = UserSerializer(user)
        return Response(serializer.data)


class AccountInfoView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    Account Info Resource
    Manage current user's account info
    """
    queryset = get_user_model().objects.all()
    serializer_class = AccountInfoSerializer
    permission_classes = [DRYPermissions]

    def get_object(self):
        user = self.request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None

    @list_route(
        methods=['post'], url_path='deactivate',
        permission_classes=[IsAuthenticated]
    )
    def deactivate(self, request):
        user = self.get_object()
        if not user:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not authenticated'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        user.is_active = False  # deactivate user
        user.save()

        logout(request)  # Log out the user

        serializer = self.get_serializer(instance=user)
        return Response(serializer.data)

    @detail_route(
        methods=['post'], url_path='download',
        renderer_classes=[PDFRenderer, StaticHTMLRenderer],
        permission_classes=[AllowAny]
    )
    def download(self, request):
        visitor = self.get_object()
        if not visitor:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not an email visitor'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = self.get_serializer(instance=visitor)
        return Response(serializer.data)


class UserViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    User Resource
    """
    queryset = get_user_model().objects.filter(is_active=True).order_by('first_name', 'last_name')
    serializer_class = UserSerializer
    permission_classes = [DRYPermissions]
    lookup_url_kwarg = 'user_id'
    lookup_field = 'id'
    lookup_value_regex = '[^/]+'
    filter_class = UserFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserFilterBackend,)
    search_fields = ('^username', '^first_name', '^last_name', '=email')

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        user_id = self.kwargs[lookup_url_kwarg]
        if re.match(r'[^\d]', user_id):
            self.lookup_field = 'username'
        return super(UserViewSet, self).get_object()

    def get_serializer_class(self):
        if self.request.GET.get('simple', False):
            return SimpleUserSerializer
        return self.serializer_class

    @detail_route(
        methods=['get'], url_path='download/profile',
        renderer_classes=[PDFRenderer, StaticHTMLRenderer],
        permission_classes=[AllowAny]
    )
    def download_profile(self, request, user_id=None):
        """
        Download User Profile Endpoint
        ---
        omit_serializer: True
        omit_parameters:
            - query
        """
        current_url = '%s?%s' % (
            reverse(request.resolver_match.url_name, kwargs={'user_id': user_id}),
            urlencode(request.query_params)
        )
        login_url = '/signin?next=%s' % quote_plus(current_url)
        if not request.user.is_authenticated():
            return redirect(login_url)

        user = get_object_or_404(self.get_queryset(), pk=user_id)

        try:
            self.check_object_permissions(request, user)
        except NotAuthenticated:
            return redirect(login_url)
        except PermissionDenied:
            return HttpResponse("You do not have permission to access this estimate")

        ctx = {
            'user': user,
            'profile': user.profile,
            'work': user.work_set.all(),
            'education': user.education_set.all(),
            'project': user.profileproject_set.all()
        }

        rendered_html = render_to_string("tunga/pdf/profile.html", context=ctx).encode(encoding="UTF-8")

        if request.accepted_renderer.format == 'html':
            return HttpResponse(rendered_html)

        pdf_file = HTML(string=rendered_html, encoding='utf-8').write_pdf()
        http_response = HttpResponse(pdf_file, content_type='application/pdf')
        http_response['Content-Disposition'] = 'filename="developer_profile.pdf"'
        return http_response

    @detail_route(
        methods=['post'], url_path='request',
        permission_classes=[IsAuthenticated]
    )
    def request(self, request, user_id=None):
        """
        Request User Endpoint
        ---
        omit_serializer: True
        omit_parameters:
            - query
        """
        user = get_object_or_404(self.get_queryset(), pk=user_id)

        UserRequest.objects.create(user=user, created_by=request.user)

        return Response({'message': 'Developer request sent'})


class EmailVisitorView(generics.CreateAPIView, generics.RetrieveAPIView):
    """
    Email Visitor resource.
    Manages sessions for email only visitors
    """
    queryset = EmailVisitor.objects.all()
    serializer_class = EmailVisitorSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        email = get_session_visitor_email(self.request)
        if email:
            try:
                # Visitor email logins will be valid for an hour
                return EmailVisitor.objects.get(email=email, last_login_at__gte=(
                    datetime.datetime.utcnow() - datetime.timedelta(hours=1)))
            except:
                pass
        return None

    def retrieve(self, request, *args, **kwargs):
        visitor = self.get_object()
        if not visitor:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not an email visitor'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = self.get_serializer(instance=visitor)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = EmailVisitorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visitor = serializer.save()
        create_email_visitor_session(request, visitor.email)
        return Response(serializer.data)


def social_login_view(request, provider=None):
    action = request.GET.get(SOCIAL_CONNECT_ACTION)

    next_url = request.GET.get(SOCIAL_CONNECT_NEXT)
    if next_url:
        request.session[SOCIAL_CONNECT_NEXT] = next_url
    try:
        task = int(request.GET.get(SOCIAL_CONNECT_TASK))
    except:
        task = None

    if task:
        request.session[SOCIAL_CONNECT_TASK] = task

    try:
        project = int(request.GET.get(SOCIAL_CONNECT_PROJECT))
    except:
        project = None

    if project:
        request.session[SOCIAL_CONNECT_PROJECT] = project

    if action == SOCIAL_CONNECT_ACTION_CONNECT or provider in [
        BTC_WALLET_PROVIDER_COINBASE,
        APP_INTEGRATION_PROVIDER_SLACK,
        APP_INTEGRATION_PROVIDER_HARVEST
    ]:

        if provider == BTC_WALLET_PROVIDER_COINBASE:
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('coinbase-connect-callback'))
            return redirect(coinbase_utils.get_authorize_url(redirect_uri))
        elif provider == APP_INTEGRATION_PROVIDER_SLACK:
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('slack-connect-callback'))
            return redirect(slack_utils.get_authorize_url(redirect_uri))

    enabled_providers = [FacebookProvider.id, GoogleProvider.id, GitHubProvider.id, SlackProvider.id]

    try:
        user_type = int(request.GET.get(SOCIAL_CONNECT_USER_TYPE))
    except:
        user_type = None

    if action == SOCIAL_CONNECT_ACTION_REGISTER:
        if user_type in [USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER]:
            request.session[SOCIAL_CONNECT_USER_TYPE] = user_type
        else:
            return redirect('/signup/')

    if provider in enabled_providers:
        authorize_url = '/accounts/%s/login/' % provider
        if provider == GitHubProvider.id and action == SOCIAL_CONNECT_ACTION_CONNECT:
            scope = ','.join(GITHUB_SCOPES)
            authorize_url += '?scope=%s&process=connect' % scope
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('github-connect-callback'))
            if redirect_uri:
                request.session[SOCIAL_CONNECT_CALLBACK] = redirect_uri
    else:
        authorize_url = '/'
    return redirect(authorize_url)


def payoneer_sign_up(request):
    """
    View handles and processes request to generate payoneer signup url

    * It runs a counter request using python requests

    @return: Returns generated url from payoneer systems
    """
    next_url = '{}?status=pending'.format(request.GET.get('next_url', '{}/settings/payment/'.format(TUNGA_URL)))
    error_url = request.GET.get('error_url', None)
    user = request.user
    if user and user.is_authenticated() and (user.is_developer or user.is_project_manager):
        payoneer_client = payoneer_utils.get_client(
            settings.PAYONEER_USERNAME, settings.PAYONEER_PASSWORD,
            settings.PAYONEER_PARTNER_ID
        )

        try:
            response = payoneer_client.sign_up_auto_populate(
                user.id,
                dict(
                    first_name=user.first_name, last_name=user.last_name,
                    email=user.email, phone_number=user.phone_number,
                    redirect_url=next_url
                )
            )
        except:
            return redirect(payoneer_utils.generate_error_redirect_url(HTTP_500_INTERNAL_SERVER_ERROR, url=error_url))

        try:
            payoneer_url = response.get("token")
            if payoneer_url:
                user.payoneer_signup_url = payoneer_url
                user.payoneer_status = STATUS_INITIATED
                user.save()
                return redirect(payoneer_url)
            else:
                return redirect(payoneer_utils.generate_error_redirect_url(HTTP_400_BAD_REQUEST, url=error_url))
        except:
            return redirect(payoneer_utils.generate_error_redirect_url(HTTP_500_INTERNAL_SERVER_ERROR, url=error_url))
    else:
        return redirect(payoneer_utils.generate_error_redirect_url(HTTP_401_UNAUTHORIZED, url=error_url))


@csrf_exempt
@api_view(http_method_names=['GET'])
@permission_classes([AllowAny])
def payoneer_notification(request):
    """
    Receive Payoneer IPCN
    """
    try:
        reg_status = request.GET.get("status", "initial")

        apuid = request.GET.get("apuid", None)  # apuid --> Payee ID
        sessionid = request.GET.get("sessionid", None)  # sessionid
        payoneerid = request.GET.get("payoneerid", None)  # Payoneer ID

        if apuid and payoneerid:
            try:
                user = TungaUser.objects.get(id=apuid)
            except:
                return Response({"message": "Payee not found"}, status=HTTP_400_BAD_REQUEST)

            if user.payoneer_signup_url and reg_status in [STATUS_PENDING, STATUS_APPROVED, STATUS_DECLINED]:
                user.payoneer_status = reg_status
                user.save()

                return Response({"message": "Notification received"})
            else:
                return Response({"message": "No payoneer signup url for for user"}, status=HTTP_400_BAD_REQUEST)
        else:
            response_dict = {"message": "Unexpected return status"}
            return Response(response_dict)

    except Exception as e:
        return Response({"error": e}, status=HTTP_500_INTERNAL_SERVER_ERROR)


def coinbase_connect_callback(request):
    code = request.GET.get('code', None)
    redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse(request.resolver_match.url_name))
    r = requests.post(url=coinbase_utils.get_token_url(), data={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': COINBASE_CLIENT_ID,
        'client_secret': COINBASE_CLIENT_SECRET,
        'redirect_uri': redirect_uri
    })

    if r.status_code == 200:
        response = r.json()
        defaults = {
            'token': response['access_token'],
            'token_secret': response['refresh_token'],
            # 'expires_at': response['expires_in'] # Coinbase returns an interval here
        }
        wallet, created = BTCWallet.objects.update_or_create(
            user=request.user, provider=BTC_WALLET_PROVIDER_COINBASE, defaults=defaults
        )
        UserProfile.objects.update_or_create(user=request.user, defaults={
            'payment_method': PAYMENT_METHOD_BTC_WALLET, 'btc_wallet': wallet
        })

    return redirect('/profile/payment/coinbase/')


def github_connect_callback(request):
    task_id = get_session_task(request)
    if task_id:
        social_token = get_social_token(user=request.user, provider=GitHubProvider.id)
        if not social_token:
            return Response({'status': 'Unauthorized'}, status.HTTP_401_UNAUTHORIZED)

        token_info = dict(
            token=social_token.token,
            token_secret=social_token.token_secret,
            token_expires_at=social_token.expires_at
        )

        save_task_integration_meta(task_id, GitHubProvider.id, token_info)

    return redirect(get_session_next_url(request, provider=GitHubProvider.id))


def slack_connect_callback(request):
    code = request.GET.get('code', None)
    redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse(request.resolver_match.url_name))
    r = requests.post(url=slack_utils.get_token_url(), data={
        'code': code,
        'client_id': SLACK_CLIENT_ID,
        'client_secret': SLACK_CLIENT_SECRET,
        'redirect_uri': redirect_uri
    })

    if r.status_code == 200:
        response = r.json()
        defaults = {
            'token': response['access_token'],
            'extra': json.dumps(response)
        }
        AppIntegration.objects.update_or_create(
            user=request.user, provider=APP_INTEGRATION_PROVIDER_SLACK, defaults=defaults
        )

        project_id = get_session_project(request)
        task_id = get_session_task(request)
        if project_id or task_id:
            token_info = {
                'token': response['access_token'],
                'token_extra': json.dumps(response),
                'team_name': response['team_name'],
                'team_id': response['team_id'],
            }

            if 'bot' in response:
                token_info['bot_access_token'] = response['bot'].get('bot_access_token')
                token_info['bot_user_id'] = response['bot'].get('bot_user_id')

            if project_id:
                meta_info = dict()

                slack_client = Slacker(response['access_token'])
                channel_response = slack_client.channels.list(exclude_archived=True)
                if channel_response.successful:
                    channels = channel_response.body.get(slack_utils.KEY_CHANNELS, None)

                    if channels:
                        simple_channels = []

                        for channel in channels:
                            simple_channels.append(
                                dict(
                                    id=channel.get('id', None),
                                    name=channel.get('name', None)
                                )
                            )

                        meta_info['slack_channels'] = json.dumps(simple_channels)

                groups_response = slack_client.groups.list(exclude_archived=True)
                if groups_response.successful:
                    groups = groups_response.body.get(slack_utils.KEY_GROUPS, None)

                    if groups:
                        simple_groups = []

                        for group in groups:
                            simple_groups.append(
                                dict(
                                    id=group.get('id', None),
                                    name=group.get('name', None)
                                )
                            )

                        meta_info['slack_groups'] = json.dumps(simple_groups)

                for meta_key in token_info:
                    meta_info['slack_{}'.format(meta_key)] = token_info[meta_key]
                save_project_metadata(project_id, meta_info)
            if task_id:
                save_task_integration_meta(task_id, APP_INTEGRATION_PROVIDER_SLACK, token_info)

    return redirect(get_session_next_url(request, provider=APP_INTEGRATION_PROVIDER_SLACK))


@api_view(('GET',))
@renderer_classes((JSONRenderer, ))
def exact_connect_callback(request):
    code = request.GET.get('code', None)
    if code:
        exact_api = exact_utils.get_api()
        exact_api.request_token(code)
        return Response({'message': 'Exact tokens updated'})
    return Response({'message', 'Bad request'}, status=HTTP_400_BAD_REQUEST)


class DevelopersSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.5

    def items(self):
        return TungaUser.objects.filter(type=USER_TYPE_DEVELOPER, verified=True)

    def lastmod(self, obj):
        return obj.date_joined
