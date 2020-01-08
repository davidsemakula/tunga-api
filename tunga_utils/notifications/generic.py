from django_rq import job

from tunga_utils.notifications.email import notify_new_contact_request_email, \
    notify_new_developer_request_email
from tunga_utils.notifications.slack import notify_new_invite_request_slack


@job
def notify_new_contact_request(contact_request):
    notify_new_contact_request_email(contact_request)


@job
def notify_new_invite_request(invite_request):
    notify_new_developer_request_email(invite_request)
    notify_new_invite_request_slack(invite_request)
