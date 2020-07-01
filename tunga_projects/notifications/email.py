import datetime

from django_rq import job

from tunga.settings import TUNGA_URL, MANDRILL_VAR_FIRST_NAME
from tunga_projects.models import Participation, ProgressReport, ProgressEvent, InterestPoll, \
    Project
from tunga_settings.slugs import NEW_TASK_PROGRESS_REPORT_EMAIL, TASK_SURVEY_REMINDER_EMAIL
from tunga_settings.utils import check_switch_setting
from tunga_utils import mandrill_utils
from tunga_utils.constants import PROGRESS_EVENT_MILESTONE, \
    PROGRESS_EVENT_DEVELOPER, PROGRESS_EVENT_PM, PROGRESS_EVENT_INTERNAL, \
    PROGRESS_EVENT_CLIENT, \
    STATUS_ACCEPTED, PROGRESS_EVENT_DEVELOPER_RATING
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance


@job
def notify_new_participant_email_dev(participation):
    participation = clean_instance(participation, Participation)

    subject = "Project invitation from {}".format(participation.created_by.first_name)
    to = [participation.user.email]
    ctx = {
        'inviter': participation.created_by,
        'invitee': participation.user,
        'project': participation.project,
        'project_url': '{}/projects/{}/'.format(TUNGA_URL, participation.project.id)
    }
    send_mail(
        subject, 'tunga/email/project_invitation', to, ctx
    )


@job
def remind_progress_event_email(progress_event):
    progress_event = clean_instance(progress_event, ProgressEvent)

    if progress_event.last_reminder_at:
        # No double notifications
        return

    is_client_event = progress_event.type in [PROGRESS_EVENT_CLIENT, PROGRESS_EVENT_MILESTONE, PROGRESS_EVENT_DEVELOPER_RATING]
    is_pm_event = progress_event.type in [PROGRESS_EVENT_PM, PROGRESS_EVENT_INTERNAL, PROGRESS_EVENT_MILESTONE]
    is_dev_event = progress_event.type in [PROGRESS_EVENT_DEVELOPER, PROGRESS_EVENT_MILESTONE]

    successful_sends = []

    owner = progress_event.project.owner or progress_event.project.user
    pm = progress_event.project.pm
    project = clean_instance(progress_event.project.id, Project)
    participants = project.participation_set.filter(status=STATUS_ACCEPTED)

    ctx = {
        'project': project,
        'participants': participants,
        'owner': owner,
        'event': progress_event,
        'rating_url': '%s/surveys/client/%s/' % (TUNGA_URL, project.id),
        'update_url': '%s/projects/%s/events/%s/' % (TUNGA_URL, progress_event.project.id, progress_event.id)
    }

    if is_client_event and owner and owner.is_active and check_switch_setting(owner, TASK_SURVEY_REMINDER_EMAIL):
        subject = "Progress Survey"
        to = [owner.email]

        if send_mail(subject, 'tunga/email/client_survey_reminder_v3', to, ctx):
            successful_sends.append('client')

    if is_pm_event and pm and pm.is_active:
        subject = "Upcoming progress update"
        to = [pm.email]

        if send_mail(subject, 'tunga/email/progress_event_reminder_v3', to, ctx, bcc=None):
            successful_sends.append('pm')

    if is_dev_event:
        subject = "Upcoming progress update"

        participants = progress_event.project.participation_set.filter(status=STATUS_ACCEPTED, updates_enabled=True)
        if participants:
            to = [participants[0].user.email]
            bcc = [participant.user.email for participant in participants[1:]] if participants.count() > 1 else None

            if send_mail(subject, 'tunga/email/progress_event_reminder_v3', to, ctx, bcc=bcc):
                successful_sends.append('devs')

    if successful_sends:
        progress_event.last_reminder_at = datetime.datetime.utcnow()
        progress_event.save()


@job
def notify_new_progress_report_email_client(progress_report):
    progress_report = clean_instance(progress_report, ProgressReport)

    is_dev_report = progress_report.event.type == PROGRESS_EVENT_DEVELOPER or \
                    (progress_report.event.type == PROGRESS_EVENT_MILESTONE and progress_report.user.is_developer)

    if not is_dev_report:
        # Only dev reports are sent by email to clients
        return

    subject = "{} submitted a Progress Report".format(
        progress_report.user.display_name.encode('utf-8')
    )

    to = []
    if is_dev_report:
        owner = progress_report.event.project.owner or progress_report.event.project.user
        if owner and check_switch_setting(owner, NEW_TASK_PROGRESS_REPORT_EMAIL):
            to.append(owner.email)
            creator = progress_report.event.project.user
            if creator and creator.id != owner.id and check_switch_setting(creator, NEW_TASK_PROGRESS_REPORT_EMAIL):
                to.append(creator.email)
        # TODO: Re-enable admins
        # admins = progress_report.event.project.admins
        # if admins:
        #    to.extend([user.email for user in admins])

    if not to:
        # Should have some recipients
        return



    ctx = {
        'owner': progress_report.event.project.owner or progress_report.event.project.user,
        'reporter': progress_report.user,
        'event': progress_report.event,
        'report': progress_report,
        'update_url': '{}/projects/{}/events/{}/'.format(TUNGA_URL, progress_report.event.project.id, progress_report.event.id)
    }

    send_mail(
        subject, 'tunga/email/new_progress_report', to, ctx
    )


@job
def notify_interest_poll_email(interest_poll, reminder=False):
    interest_poll = clean_instance(interest_poll, InterestPoll)

    to = [interest_poll.user.email]
    subject = 'New project opportunity: %s' % interest_poll.project.title
    if reminder:
        subject = 'Reminder for project opportunity: %s' % interest_poll.project.title

    poll_url = '{}/projects/{}'.format(TUNGA_URL, interest_poll.project.id)

    merge_vars = [
        mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, interest_poll.user.first_name),
        mandrill_utils.create_merge_var('opportunity_title', interest_poll.project.title),
        mandrill_utils.create_merge_var('skills', str(interest_poll.project.skills)),
        mandrill_utils.create_merge_var('description', interest_poll.project.description),
        mandrill_utils.create_merge_var('scope', interest_poll.project.get_expected_duration_display()),
        mandrill_utils.create_merge_var('project_url', poll_url),
    ]

    mandrill_response = mandrill_utils.send_email(
        reminder and '103b-new-project-opportunity-reminder' or '103-new-project-opportunity',
        to, merge_vars=merge_vars, subject=subject
    )
    if mandrill_response:
        if reminder:
            interest_poll.reminded_at = datetime.datetime.utcnow()
        else:
            interest_poll.sent_at = datetime.datetime.utcnow()
        interest_poll.save()

        mandrill_utils.log_emails.delay(mandrill_response, to)
