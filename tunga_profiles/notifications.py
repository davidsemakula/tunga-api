import datetime

from django.contrib.auth import get_user_model
from django_rq.decorators import job

from tunga.settings import TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, TUNGA_URL, \
    SLACK_STAFF_INCOMING_WEBHOOK, \
    SLACK_ATTACHMENT_COLOR_GREEN, SLACK_ATTACHMENT_COLOR_RED, \
    SLACK_STAFF_PROFILES_CHANNEL, SLACK_STAFF_LEADS_CHANNEL, \
    SLACK_STAFF_PLATFORM_ALERTS
from tunga_profiles.models import DeveloperApplication, Skill, \
    DeveloperInvitation, UserProfile, UserRequest
from tunga_tasks.models import Task
from tunga_utils import slack_utils
from tunga_utils.constants import USER_TYPE_DEVELOPER
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance


@job
def send_new_developer_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "{} has applied to become a Tunga developer".format(
        instance.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'application': instance,
    }
    send_mail(subject, 'tunga/email/new_developer_application', to, ctx)


@job
def send_developer_application_received_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "Your application to become a Tunga developer has been received"
    to = [instance.email]
    ctx = {
        'application': instance
    }
    send_mail(subject, 'tunga/email/developer_application_received', to, ctx)


@job
def send_developer_accepted_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "Your application to become a Tunga developer has been accepted"
    to = [instance.email]
    ctx = {
        'application': instance,
        'invite_url': '%s/signup/developer/%s/' % (
            TUNGA_URL, instance.confirmation_key)
    }
    if send_mail(subject, 'tunga/email/developer_application_accepted', to,
                 ctx):
        instance.confirmation_sent_at = datetime.datetime.utcnow()
        instance.save()


@job
def send_new_skill_email(instance):
    instance = clean_instance(instance, Skill)
    subject = "New skill created"
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS

    users = get_user_model().objects.filter(userprofile__skills=instance)
    tasks = Task.objects.filter(skills=instance)
    ctx = {
        'skill': instance.name,
        'users': users,
        'tasks': tasks
    }
    send_mail(subject, 'tunga/email/new_skill', to, ctx)


@job
def send_developer_invited_email(instance, resend=False,
                                 transfer_from_sso=False):
    instance = clean_instance(instance, DeveloperInvitation)
    subject = "You have been invited to become a Tunga {}".format(
        instance.display_type.lower()
    )
    to = [instance.email]
    ctx = {
        'invite': instance,
        'invite_url': '%s/signup/invite/%s/' % (
        TUNGA_URL, instance.invitation_key,),
        'tunga_platform': TUNGA_URL
    }

    if transfer_from_sso:
        subject = "You have been granted access to Tunga Platform"
        send_mail(subject, 'tunga/email/user_invitation_by_transfer', to, ctx)
        instance.used = True
        instance.invitation_sent_at = datetime.datetime.utcnow()
        instance.used_at = datetime.datetime.utcnow()
        instance.save()
        notify_user_has_been_invited_to_developer_slack(instance)
    else:
        if send_mail(subject, 'tunga/email/user_invitation', to, ctx):
            if resend:
                instance.used = False
                instance.resent = True
                instance.resent_at = datetime.datetime.utcnow()
            else:
                instance.invitation_sent_at = datetime.datetime.utcnow()
            instance.save()

            if not resend:
                notify_user_has_been_invited_to_developer_slack(instance)


@job
def send_developer_invitation_accepted_email(instance):
    instance = clean_instance(instance, DeveloperInvitation)
    subject = "{} has accepted your invitation to become a Tunga {}".format(
        instance.first_name,
        instance.display_type.lower()
    )
    to = [instance.created_by.email]
    ctx = {
        'invite': instance
    }
    send_mail(subject, 'tunga/email/user_invitation_accepted', to, ctx)


@job
def notify_user_profile_updated_slack(instance, edited=None):
    instance = clean_instance(instance, UserProfile)

    if instance.user.type != USER_TYPE_DEVELOPER:
        return

    profile_url = '{}/developer/{}'.format(TUNGA_URL, instance.user.username)
    slack_msg = "{}'s profile has been updated | <{}|Review on Tunga>".format(
        instance.user.display_name,
        profile_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.user.display_name,
            slack_utils.KEY_TITLE_LINK: profile_url,
            slack_utils.KEY_TEXT: '*Name:* {}\n'
                                  '*Location:* {}\n'
                                  '*Skills*: {}\n'
                                  '*Verified:* {}'.format(
                instance.user.display_name,
                instance.location,
                str(instance.skills),
                instance.user.verified and 'True' or 'False'
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: instance.user.verified and SLACK_ATTACHMENT_COLOR_GREEN or SLACK_ATTACHMENT_COLOR_RED
        }
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_PROFILES_CHANNEL
        }
    )


@job
def notify_user_request_slack(instance):
    instance = clean_instance(instance, UserRequest)

    if instance.user.type != USER_TYPE_DEVELOPER:
        # Only send requests for devs
        return

    requester_url = '{}/network/{}'.format(TUNGA_URL,
                                           instance.created_by.username)
    requestee_url = '{}/network/{}'.format(TUNGA_URL, instance.user.username)
    slack_msg = "<{}|{}> requested to work with <{}|{}>".format(
        requester_url,
        instance.created_by.display_name,
        requestee_url,
        instance.user.display_name,
    )

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_LEADS_CHANNEL
        }
    )


@job
def notify_user_has_been_invited_to_developer_slack(instance):
    instance = clean_instance(instance, DeveloperInvitation)
    slack_msg = "{} has been invited to become a Tunga {}".format(
        instance.first_name,
        instance.display_type.lower()
    )

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_PLATFORM_ALERTS
        }
    )


@job
def notify_tunga_new_skill_has_been_added(instance):
    instance = clean_instance(instance, Skill)

    slack_msg = "{} has been added as a new skill".format(
        instance.name,
    )

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_PLATFORM_ALERTS
        }
    )
