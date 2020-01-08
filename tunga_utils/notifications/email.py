import datetime

from django_rq.decorators import job

from tunga.settings import TUNGA_CONTACT_REQUEST_EMAIL_RECIPIENTS, \
    SLACK_STAFF_INCOMING_WEBHOOK, \
    SLACK_STAFF_PLATFORM_ALERTS, MANDRILL_VAR_FIRST_NAME
from tunga_utils import slack_utils, mandrill_utils
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance
from tunga_utils.models import ContactRequest, InviteRequest


@job
def notify_new_contact_request_email(contact_request):
    contact_request = clean_instance(contact_request, ContactRequest)

    if contact_request.body:
        slack_msg = '{} {} is inquiring about {}'.format(
            contact_request.fullname,
            contact_request.email,
            contact_request.body,
        )

        slack_utils.send_incoming_webhook(
            SLACK_STAFF_INCOMING_WEBHOOK,
            {
                slack_utils.KEY_TEXT: slack_msg,
                slack_utils.KEY_CHANNEL: SLACK_STAFF_PLATFORM_ALERTS
            }
        )

    else:
        subject = "New {} Request".format(
            contact_request.item and 'Offer' or 'Contact')
        msg_suffix = 'wants to know more about Tunga.'
        if contact_request.item:
            item_name = contact_request.get_item_display()
            subject = '%s (%s)' % (subject, item_name)
            msg_suffix = 'requested for "%s"' % item_name
        to = TUNGA_CONTACT_REQUEST_EMAIL_RECIPIENTS

        ctx = {
            'email': contact_request.email,
            'message': '%s %s ' % (
                contact_request.email,
                msg_suffix
            )
        }

        slack_msg = "%s %s" % (subject, msg_suffix)

        if slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK,
                                             {
                                                 slack_utils.KEY_TEXT: slack_msg,
                                                 slack_utils.KEY_CHANNEL: SLACK_STAFF_PLATFORM_ALERTS
                                             }
                                             ):
            contact_request.email_sent_at = datetime.datetime.utcnow()
            contact_request.save()


@job
def notify_new_developer_request_email(invite_request):
    invite_request = clean_instance(invite_request, InviteRequest)
    to = [invite_request.email]

    merge_vars = [
        mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME,
                                        invite_request.name),
    ]

    mandrill_response = mandrill_utils.send_email('110-developer-submitted-an-application', to, merge_vars=merge_vars)
    if mandrill_response:
        invite_request.email_sent_at = datetime.datetime.utcnow()
        invite_request.save()
