"""tunga URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from allauth.account.views import ConfirmEmailView
from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth.views import password_reset_confirm
from django.contrib.sitemaps.views import sitemap
from rest_auth.views import UserDetailsView
from rest_framework.routers import DefaultRouter
from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token, \
    verify_jwt_token
from rest_framework_swagger.views import get_swagger_view

from tunga import settings
from tunga_activity.views import ActionViewSet, NotificationReadLogViewSet
from tunga_auth.views import VerifyUserView, AccountInfoView, UserViewSet, \
    social_login_view, coinbase_connect_callback, \
    slack_connect_callback, EmailVisitorView, github_connect_callback, \
    DevelopersSitemap, \
    payoneer_sign_up, payoneer_notification, exact_connect_callback
from tunga_comments.views import CommentViewSet
from tunga_messages.views import MessageViewSet, ChannelViewSet, \
    slack_customer_notification
from tunga_pages.views import SkillPageViewSet, SkillPagesSitemap, \
    BlogPostViewSet, BlogSitemap
from tunga_payments.views import InvoiceViewSet, PaymentViewSet
from tunga_profiles.views import ProfileView, EducationViewSet, WorkViewSet, \
    NotificationView, CountryListView, \
    DeveloperApplicationViewSet, RepoListView, IssueListView, \
    SlackIntegrationView, \
    DeveloperInvitationViewSet, CompanyView, WhitePaperVisitorsView
from tunga_projects.views import ProjectViewSet, DocumentViewSet, \
    ParticipationViewSet, ProgressEventViewSet, \
    ProgressReportViewSet, InterestPollViewSet, DeveloperRatingViewSet, \
    ClientSurveyTemplate, ClientSurveyFormView, ClientSurveySuccessTemplate, \
    ClientSurveyErrorTemplate, ClientSurveyFilledTemplate
from tunga_settings.views import UserSettingsView
from tunga_tasks.views import coinbase_notification, bitpesa_notification, \
    TaskViewSet
from tunga_uploads.views import UploadViewSet
from tunga_utils.views import SkillViewSet, ContactRequestView, \
    get_medium_posts, get_oembed_details, upload_file, \
    find_by_legacy_id, InviteRequestView, weekly_report, hubspot_notification, \
    calendly_notification, search_logger

api_schema_view = get_swagger_view(title='Tunga API')

router = DefaultRouter()
# v3 routes
router.register(r'users', UserViewSet)
router.register(r'apply', DeveloperApplicationViewSet)
router.register(r'invite', DeveloperInvitationViewSet)
router.register(r'me/account', AccountInfoView)
router.register(r'me/education', EducationViewSet)
router.register(r'me/work', WorkViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'documents', DocumentViewSet)
router.register(r'participation', ParticipationViewSet)
router.register(r'interest-polls', InterestPollViewSet)
router.register(r'progress-events', ProgressEventViewSet)
router.register(r'progress-reports', ProgressReportViewSet)
router.register(r'developer-rating', DeveloperRatingViewSet)
router.register(r'invoices', InvoiceViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'activity', ActionViewSet)
router.register(r'comments', CommentViewSet)
router.register(r'channels', ChannelViewSet)
router.register(r'messages', MessageViewSet)
router.register(r'uploads', UploadViewSet)
router.register(r'skills', SkillViewSet)
router.register(r'skill-pages', SkillPageViewSet)
router.register(r'blogs', BlogPostViewSet)
router.register(r'notification-log', NotificationReadLogViewSet)

# Legacy routes
# router.register(r'user', UserViewSet)
# router.register(r'apply', DeveloperApplicationViewSet)
# router.register(r'invite', DeveloperInvitationViewSet)
# router.register(r'project', LegacyProjectViewSet)
router.register(r'task', TaskViewSet)
# router.register(r'application', ApplicationViewSet)
# router.register(r'participation', LegacyParticipationViewSet)
# router.register(r'estimate', EstimateViewSet)
# router.register(r'quote', QuoteViewSet)
# router.register(r'sprint', SprintViewSet)
# router.register(r'time-entry', TimeEntryViewSet)

# router.register(r'connection', ConnectionViewSet)
# router.register(r'channel', ChannelViewSet)
# router.register(r'message', MessageViewSet)
# router.register(r'skill', SkillViewSet)
# router.register(r'support/section', SupportSectionViewSet)
# router.register(r'support/page', SupportPageViewSet)
# router.register(r'multi-task-payment', MultiTaskPaymentKeyViewSet)
# router.register(r'task-payment', TaskPaymentViewSet)
# router.register(r'participant-payment', ParticipantPaymentViewSet)
# router.register(r'skill-page', SkillPageViewSet)
# router.register(r'skill-approval', SkillsApprovalViewSet)
# router.register(r'blog', BlogPostViewSet)
# router.register(r'task-document', TaskDocumentViewSet)

# Dictionary containing your sitemap classes
sitemaps = {
    'blog': BlogSitemap(),
    'skills': SkillPagesSitemap(),
    'developers': DevelopersSitemap(),
}

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^admin/django-rq/', include('django_rq.urls')),
    url(r'^accounts/social/(?P<provider>\w+)/$', social_login_view, name="social-login-redirect"),
    url(r'^accounts/coinbase/login/callback/$', coinbase_connect_callback, name="coinbase-connect-callback"),
    url(r'^accounts/slack/connect/callback/$', slack_connect_callback, name="slack-connect-callback"),
    url(r'^accounts/github/connect/callback/$', github_connect_callback, name="github-connect-callback"),
    url(r'^accounts/exact/connect/callback/$', exact_connect_callback, name="exact-connect-callback"),
    url(r'^accounts/', include('allauth.urls')),
    url(r'api/', include(router.urls)),
    url(r'^api/auth/register/account-confirm-email/(?P<key>\w+)/$', ConfirmEmailView.as_view(),
        name='account_confirm_email'),
    url(r'^api/auth/register/', include('rest_auth.registration.urls')),
    url(r'^api/auth/verify/', VerifyUserView.as_view(), name='auth-verify'),
    url(r'^api/auth/visitor/', EmailVisitorView.as_view(), name='auth-visitor'),
    url(r'^api/auth/jwt/token/', obtain_jwt_token),
    url(r'^api/auth/jwt/refresh/', refresh_jwt_token),
    url(r'^api/auth/jwt/verify/', verify_jwt_token),
    url(r'^api/oauth/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    #url(r'^api/me/account/', AccountInfoView.as_view(), name='account-info'),
    url(r'^api/me/user/', UserDetailsView.as_view(), name='user-info'),
    url(r'^api/me/profile/', ProfileView.as_view(), name='profile-info'),
    url(r'^api/me/company/', CompanyView.as_view(), name='company-info'),
    url(r'^api/me/settings/', UserSettingsView.as_view(), name='user-settings'),
    url(r'^api/me/notification/', NotificationView.as_view(), name='user-notifications'),
    url(r'^api/me/app/(?P<provider>\w+)/repos/$', RepoListView.as_view(), name="repo-list"),
    url(r'^api/me/app/(?P<provider>\w+)/issues/$', IssueListView.as_view(), name="issue-list"),
    url(r'^api/me/app/slack/$', SlackIntegrationView.as_view(), name="slack-app"),
    url(r'^api/me/app/slack/(?P<resource>\w+)/$', SlackIntegrationView.as_view(), name="slack-app-resource"),
    url(r'^api/hook/coinbase/$', coinbase_notification, name="coinbase-notification"),
    url(r'^api/hook/bitpesa/$', bitpesa_notification, name="bitpesa-notification"),
    url(r'^api/hook/slack/customer/$', slack_customer_notification, name="slack-customer-notification"),
    url(r'^api/hook/hubspot/$', hubspot_notification, name="hubspot-notification"),
    url(r'^api/hook/calendly/$', calendly_notification, name="calendly-notification"),
    url(r'^api/auth/', include('rest_auth.urls')),
    url(r'api/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api/countries/', CountryListView.as_view(), name='countries'),
    url(r'^api/contact-request/', ContactRequestView.as_view(), name='contact-request'),
    url(r'^api/invite-request/', InviteRequestView.as_view(), name='invite-request'),
    url(r'^api/medium/', get_medium_posts, name='medium-posts'),
    url(r'^api/log/search/$', search_logger, name="search-logger"),
    url(r'^api/oembed/', get_oembed_details, name='oembed-details'),
    url(r'^api/upload/', upload_file, name='upload-file'),
    url(r'^api/docs/', api_schema_view),
    url(r'^api/payoneer/ipcn/callback/', payoneer_notification, name="payoneer-ipcn-status"),
    url(r'^api/payoneer/', payoneer_sign_up, name="payoneer"),
    url(r'^reset-password/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        password_reset_confirm, name='password_reset_confirm'),
    url(r'^api/migrate/(?P<model>\w+)/(?P<pk>\d+)/$', find_by_legacy_id, name="migrate"),
    url(r'^api/weekly-report/(?P<subject>\w+)/$', weekly_report, name="weekly-report"),
    url(r'^$', router.get_api_root_view(), name='backend-root'),
    url(r'^api/sitemap\.xml$', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    url(r'^api/visitors/$', WhitePaperVisitorsView.as_view(), name="visiotrs_email"),

    url(r'^surveys/client/(?P<id>\d+)/$', ClientSurveyTemplate.as_view(), name="client_survey"),
    url(r'^surveys/client/success/$', ClientSurveySuccessTemplate.as_view(), name="client_survey_success"),
    url(r'^surveys/client/error/$', ClientSurveyErrorTemplate.as_view(), name="client_survey_error"),
    url(r'^surveys/client/submitted/$', ClientSurveyFilledTemplate.as_view(), name="client_survey_submitted"),
    url(r'^surveys/client/(?P<id>\d+)/created/$', ClientSurveyFormView.as_view(), name="client_survey_submit"),

]
