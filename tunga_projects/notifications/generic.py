from django_rq import job

from tunga_projects.notifications.email import notify_new_participant_email_dev, \
    notify_new_progress_report_email_client, remind_progress_event_email
from tunga_projects.notifications.slack import notify_new_progress_report_slack, \
    notify_missed_progress_event_slack, notify_new_project_slack, \
    notify_interest_poll_status_slack, notify_new_developer_rating_slack


@job
def notify_new_project(project):
    notify_new_project_slack(project)


@job
def notify_new_participant(participation):
    notify_new_participant_email_dev(participation)


@job
def remind_progress_event(progress_event):
    remind_progress_event_email(progress_event)


@job
def notify_new_progress_report(progress_report):
    notify_new_progress_report_email_client(progress_report)
    notify_new_progress_report_slack(progress_report, updated=False)


@job
def notify_new_developer_rating(developer_rating):
    notify_new_developer_rating_slack(developer_rating, updated=False)


@job
def notify_missed_progress_event(progress_event):
    notify_missed_progress_event_slack(progress_event)


@job
def notify_interest_poll_status(interest_poll):
    notify_interest_poll_status_slack(interest_poll)
