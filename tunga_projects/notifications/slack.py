import datetime
import os

from django.contrib.auth import get_user_model
from django.template.defaultfilters import floatformat
from django_rq import job

from tunga.settings import TUNGA_URL, SLACK_STAFF_INCOMING_WEBHOOK, \
    SLACK_STAFF_LEADS_CHANNEL, \
    SLACK_ATTACHMENT_COLOR_TUNGA, SLACK_ATTACHMENT_COLOR_GREEN, \
    SLACK_STAFF_UPDATES_CHANNEL, SLACK_ATTACHMENT_COLOR_RED, \
    SLACK_ATTACHMENT_COLOR_NEUTRAL, SLACK_ATTACHMENT_COLOR_BLUE, \
    SLACK_STAFF_MISSED_UPDATES_CHANNEL, \
    SLACK_DEVELOPER_INCOMING_WEBHOOK, SLACK_DEVELOPER_OPPORTUNITIES_CHANNEL, \
    MEDIA_ROOT, SLACK_STAFF_TOKEN, \
    SLACK_STAFF_REPORTS_CHANNEL, SLACK_STAFF_PLATFORM_ALERTS
from tunga_projects.models import Project, ProgressReport, ProgressEvent, \
    InterestPoll, DeveloperRating
from tunga_projects.utils import weekly_project_report, weekly_payment_report
from tunga_utils import slack_utils
from tunga_utils.constants import PROGRESS_EVENT_PM, PROGRESS_EVENT_INTERNAL, \
    PROGRESS_EVENT_CLIENT, \
    PROGRESS_EVENT_MILESTONE, PROJECT_STAGE_OPPORTUNITY, STATUS_INTERESTED, \
    PROGRESS_EVENT_DEVELOPER_RATING
from tunga_utils.helpers import clean_instance, convert_to_text, \
    convert_to_emoji


@job
def notify_new_project_slack(project):
    notify_new_project_slack_admin.delay(project)
    notify_project_slack_dev.delay(project)


def create_project_slack_message(project, to_developer=False, reminder=False):
    project_url = '{}/projects/{}/'.format(TUNGA_URL, project.id)

    is_opportunity = project.stage == PROJECT_STAGE_OPPORTUNITY

    summary = "{} {} created by {} | <{}|View on Tunga>".format(
        reminder and 'Reminder for' or 'New',
        is_opportunity and 'opportunity' or 'project',
        project.user.display_name.encode('utf-8'),
        project_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: project.title,
            slack_utils.KEY_TITLE_LINK: project_url,
            slack_utils.KEY_TEXT: project.description or project.title,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        }
    ]

    extra_details = ''
    if project.type and not is_opportunity:
        extra_details += '*Type*: {}\n'.format(project.get_type_display())
    if project.expected_duration:
        extra_details += '*Expected duration*: {}\n'.format(
            project.get_expected_duration_display())
    if project.category:
        extra_details += '*Category*: {}\n'.format(
            project.get_category_display())
    if project.skills:
        extra_details += '*Skills*: {}\n'.format(str(project.skills))
    if not is_opportunity and not to_developer:
        if project.deadline:
            extra_details += '*Deadline*: {}\n'.format(
                project.deadline.strftime("%d %b, %Y"))
        if project.budget:
            extra_details += '*Fee*: EUR {}\n'.format(
                floatformat(project.budget, arg=-2))

    if extra_details:
        attachments.append({
            slack_utils.KEY_TEXT: extra_details,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        })

    if to_developer:
        attachments.append({
            slack_utils.KEY_FALLBACK: 'Show interest at {}'.format(project_url),
            slack_utils.KEY_ACTIONS: [
                {
                    slack_utils.KEY_TYPE: slack_utils.VALUE_TYPE_BUTTON,
                    slack_utils.KEY_TEXT: "I'm interested",
                    slack_utils.KEY_URL: project_url
                }
            ],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
        })

    return summary, attachments


@job
def notify_new_project_slack_admin(project):
    project = clean_instance(project, Project)

    summary, attachments = create_project_slack_message(project)
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, {
        slack_utils.KEY_TEXT: summary,
        slack_utils.KEY_CHANNEL: SLACK_STAFF_LEADS_CHANNEL,
        slack_utils.KEY_ATTACHMENTS: attachments
    })


@job
def notify_project_slack_dev(project, reminder=False):
    project = clean_instance(project, Project)

    if project.stage != PROJECT_STAGE_OPPORTUNITY:
        # Only notify devs about opportunities
        return

    summary, attachments = create_project_slack_message(project,
                                                        to_developer=True,
                                                        reminder=reminder)
    slack_utils.send_incoming_webhook(SLACK_DEVELOPER_INCOMING_WEBHOOK, {
        slack_utils.KEY_TEXT: summary,
        slack_utils.KEY_CHANNEL: SLACK_DEVELOPER_OPPORTUNITIES_CHANNEL,
        slack_utils.KEY_ATTACHMENTS: attachments
    })


def create_progress_report_slack_message(progress_report, updated=False,
                                         to_client=False):
    is_pm_report = progress_report.event.type in [PROGRESS_EVENT_PM,
                                                  PROGRESS_EVENT_INTERNAL] or \
                   (
                       progress_report.event.type == PROGRESS_EVENT_MILESTONE and progress_report.user.is_project_manager)
    is_client_report = progress_report.event.type in [PROGRESS_EVENT_CLIENT,
                                                      PROGRESS_EVENT_DEVELOPER_RATING] or \
                       (
                           progress_report.event.type == PROGRESS_EVENT_MILESTONE and progress_report.user.is_project_owner)
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    report_url = '{}/projects/{}/events/{}/'.format(TUNGA_URL,
                                                    progress_report.event.project_id,
                                                    progress_report.event_id)
    slack_msg = "{} {} a {} | {}".format(
        progress_report.user.display_name.encode('utf-8'),
        updated and '*updated*' or 'submitted',
        is_client_report and "Client Survey" or "Progress Report",
        '<{}|View on Tunga>'.format(report_url)
    )

    slack_text_suffix = ''
    if not to_client:
        slack_text_suffix += '*Due Date:* {}\n'.format(
            progress_report.event.due_at.strftime("%d %b, %Y"))
    if not is_client_report:
        slack_text_suffix += '*Status:* {}\n*Percentage completed:* {}{}'.format(
            progress_report.get_status_display(), progress_report.percentage,
            '%')
    if not to_client:
        if progress_report.last_deadline_met is not None:
            slack_text_suffix += '\n*Was the last deadline met?:* {}'.format(
                progress_report.last_deadline_met and 'Yes' or 'No'
            )
        if progress_report.next_deadline:
            slack_text_suffix += '\n*Next deadline:* {}'.format(
                progress_report.next_deadline.strftime("%d %b, %Y"))
    if is_client_report:
        pass
        # edit - Remo
        # if progress_report.deliverable_satisfaction is not None:
        #     slack_text_suffix += '\n*Are you satisfied with the deliverables?:* {}'.format(
        #         progress_report.deliverable_satisfaction and 'Yes' or 'No'
        #     )

    if is_dev_report:
        if progress_report.stuck_reason:
            slack_text_suffix += '\n*Reason for being stuck:*\n {}'.format(
                convert_to_text(progress_report.get_stuck_reason_display())
            )
    attachments = [
        {
            slack_utils.KEY_TITLE: progress_report.event.project.title,
            slack_utils.KEY_TITLE_LINK: report_url,
            slack_utils.KEY_TEXT: slack_text_suffix,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        }
    ]

    if not to_client:
        if progress_report.deadline_miss_communicated is not None:
            attachments.append({
                slack_utils.KEY_TITLE: '{} promptly about not making the deadline?'.format(
                    is_client_report and 'Did the project manager/ developer(s) inform you' or 'Did you inform the client'),
                slack_utils.KEY_TEXT: '{}'.format(
                    progress_report.deadline_miss_communicated and 'Yes' or 'No'),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })

    if progress_report.deadline_report:
        attachments.append({
            slack_utils.KEY_TITLE: 'Report about the last deadline:',
            slack_utils.KEY_TEXT: convert_to_text(
                progress_report.deadline_report),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
        })

    if is_client_report:
        # edit - Remo
        if progress_report.rate_communication:
            attachments.append({
                slack_utils.KEY_TITLE: 'Project Rating',
                slack_utils.KEY_TEXT: '{}/5 {}'.format(
                    progress_report.rate_communication,
                    convert_to_emoji(progress_report.rate_communication)),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })
    else:
        # Status
        if progress_report.stuck_details:
            attachments.append({
                slack_utils.KEY_TITLE: 'Explain Further why you are stuck/what should be done:',
                slack_utils.KEY_TEXT: convert_to_text(
                    progress_report.stuck_details),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })

        if progress_report.started_at and not to_client:
            attachments.append({
                slack_utils.KEY_TITLE: 'When did you start this sprint/project?',
                slack_utils.KEY_TEXT: progress_report.started_at.strftime(
                    "%d %b, %Y"),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
            })

        # Last
        if progress_report.accomplished:
            attachments.append({
                slack_utils.KEY_TITLE: 'What has been accomplished since last update?',
                slack_utils.KEY_TEXT: convert_to_text(
                    progress_report.accomplished),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })
        if progress_report.rate_deliverables and not to_client:
            attachments.append({
                slack_utils.KEY_TITLE: 'Rate Deliverables:',
                slack_utils.KEY_TEXT: '{}/5'.format(
                    progress_report.rate_deliverables),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })

        # Current
        if progress_report.todo:
            attachments.append({
                slack_utils.KEY_TITLE: is_dev_report and 'What do you intend to achieve/complete today?' or 'What are the next next steps?',
                slack_utils.KEY_TEXT: convert_to_text(progress_report.todo),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })

        if not to_client:
            # Next
            if progress_report.next_deadline:
                attachments.append({
                    slack_utils.KEY_TITLE: 'When is the next deadline?',
                    slack_utils.KEY_TEXT: progress_report.next_deadline.strftime(
                        "%d %b, %Y"),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
                })

            # Keep information about failures to meet deadlines internal
            if progress_report.next_deadline_meet is not None:
                attachments.append({
                    slack_utils.KEY_TITLE: 'Do you anticipate to meet this deadline?',
                    slack_utils.KEY_TEXT: '{}'.format(
                        progress_report.next_deadline_meet and 'Yes' or 'No'),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
                })
            if progress_report.next_deadline_fail_reason:
                attachments.append({
                    slack_utils.KEY_TITLE: 'Why will you not be able to make the next deadline?',
                    slack_utils.KEY_TEXT: convert_to_text(
                        progress_report.next_deadline_fail_reason),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
                })

        if progress_report.obstacles:
            attachments.append({
                slack_utils.KEY_TITLE: 'What obstacles are impeding your progress?',
                slack_utils.KEY_TEXT: convert_to_text(
                    progress_report.obstacles),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })
        if progress_report.obstacles_prevention:
            attachments.append({
                slack_utils.KEY_TITLE: 'What could have been done to prevent this from happening?',
                slack_utils.KEY_TEXT: convert_to_text(
                    progress_report.obstacles_prevention),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })

    if is_pm_report:
        if progress_report.team_appraisal:
            attachments.append({
                slack_utils.KEY_TITLE: 'Team appraisal:',
                slack_utils.KEY_TEXT: convert_to_text(
                    progress_report.team_appraisal),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_NEUTRAL
            })

    if progress_report.remarks:
        attachments.append({
            slack_utils.KEY_TITLE: 'Other remarks or questions',
            slack_utils.KEY_TEXT: convert_to_text(progress_report.remarks),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_NEUTRAL
        })

    return slack_msg, attachments


@job
def notify_new_progress_report_slack(progress_report, updated=False):
    progress_report = clean_instance(progress_report, ProgressReport)

    is_pm_report = progress_report.event.type in [PROGRESS_EVENT_PM,
                                                  PROGRESS_EVENT_INTERNAL] or \
                   (
                       progress_report.event.type == PROGRESS_EVENT_MILESTONE and progress_report.user.is_project_manager)
    is_client_report = progress_report.event.type == PROGRESS_EVENT_CLIENT or \
                       (
                           progress_report.event.type == PROGRESS_EVENT_MILESTONE and progress_report.user.is_project_owner)
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    # All reports go to Tunga #updates Slack
    slack_msg, attachments = create_progress_report_slack_message(
        progress_report, updated=updated)
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, {
        slack_utils.KEY_TEXT: slack_msg,
        slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL,
        slack_utils.KEY_ATTACHMENTS: attachments
    })

    if is_dev_report:
        # Re-create report for clients
        # TODO: Respect client's settings
        slack_msg, attachments = create_progress_report_slack_message(
            progress_report, updated=updated, to_client=True)
        slack_utils.send_project_message(progress_report.event.project,
                                         message=slack_msg,
                                         attachments=attachments)


@job
def notify_new_developer_rating_slack(developer_rating, updated=False):
    developer_rating = clean_instance(developer_rating, DeveloperRating)

    # All reports go to Tunga #updates Slack
    slack_msg, attachments = create_developer_rating_slack_message(
        developer_rating, updated=updated)
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, {
        slack_utils.KEY_TEXT: slack_msg,
        slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL,
        slack_utils.KEY_ATTACHMENTS: attachments
    })


def create_developer_rating_slack_message(developer_rating, updated):
    report_url = '{}/projects/{}/events/{}/'.format(TUNGA_URL,
                                                    developer_rating.event.project.id,
                                                    developer_rating.event.id)
    slack_msg = "{} {} a {} | {}".format(
        developer_rating.created_by.display_name.encode('utf-8'),
        updated and '*updated*' or 'submitted',
        "Developer Rating",
        '<{}|View on Tunga>'.format(report_url)
    )

    slack_text_suffix = ''
    slack_text_suffix += '*Date:* {}\n'.format(
        developer_rating.event.created_at.strftime("%d %b, %Y"))
    slack_text_suffix += '*Project:* {}\n'.format(
        developer_rating.event.project.title)
    slack_text_suffix += '*Developer:* {}\n'.format(
        developer_rating.user.display_name)

    attachments = [{
        slack_utils.KEY_TITLE: developer_rating.event.project.title,
        slack_utils.KEY_TITLE_LINK: report_url,
        slack_utils.KEY_TEXT: slack_text_suffix,
        slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
        slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
    }, {
        slack_utils.KEY_TITLE: 'Developer Rating',
        slack_utils.KEY_TEXT: '{}/5 {}'.format(
            developer_rating.rating,
            convert_to_emoji(developer_rating.rating)),
        slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
        slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
    }]

    return slack_msg, attachments


@job
def notify_missed_progress_event_slack(progress_event):
    progress_event = clean_instance(progress_event, ProgressEvent)

    if progress_event.project.archived or progress_event.status != "missed" or not progress_event.last_reminder_at or progress_event.missed_notification_at:
        return

    participants = progress_event.participants
    if not participants:
        # No one to report or project is now closed
        return

    target_user = None
    if participants and len(participants) == 1:
        target_user = participants[0]

    project_url = '{}/projects/{}'.format(TUNGA_URL, progress_event.project.id)
    slack_msg = "`Alert (!):` {} {} for \"{}\" | <{}|View on Tunga>".format(
        target_user and '{} missed a'.format(
            target_user.short_name) or 'Missed',
        ((progress_event.type == PROGRESS_EVENT_CLIENT or progress_event.type == PROGRESS_EVENT_DEVELOPER_RATING ) and 'progress survey') or
        (
            progress_event.type == PROGRESS_EVENT_MILESTONE and 'milestone report') or
        'progress report',
        progress_event.project.title,
        project_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: progress_event.project.title,
            slack_utils.KEY_TITLE_LINK: project_url,
            slack_utils.KEY_TEXT: '*Due Date:* {}\n\n{}'.format(
                progress_event.due_at.strftime("%d %b, %Y"),
                '\n\n'.join(
                    [
                        '*Name:* {}\n'
                        '*Email:* {}{}'.format(
                            user.display_name.encode('utf-8'),
                            user.email,
                            not user.is_project_owner and user.profile and user.profile.phone_number and
                            '\n*Phone Number:* {}'.format(
                                user.profile.phone_number) or '')
                        for user in participants
                    ]
                )
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        }
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_MISSED_UPDATES_CHANNEL
        }
    )

    # Save notification time
    progress_event.missed_notification_at = datetime.datetime.now()
    progress_event.save()


@job
def notify_interest_poll_status_slack(interest_poll):
    interest_poll = clean_instance(interest_poll, InterestPoll)

    if interest_poll.project.stage != PROJECT_STAGE_OPPORTUNITY or interest_poll.status != STATUS_INTERESTED:
        # Notify only accepted opportunities
        return

    slack_msg = '<{}|{}> is interested in <{}|{}>'.format(
        '{}/network/{}'.format(TUNGA_URL, interest_poll.user.username),
        interest_poll.user.display_name,
        '{}/projects/{}'.format(TUNGA_URL, interest_poll.project.id),
        interest_poll.project.title
    )

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_LEADS_CHANNEL
        }
    )


@job
def notify_weekly_project_report_slack():
    pdf_contents = weekly_project_report(render_format='pdf')

    today = datetime.datetime.utcnow()
    filename = 'weekly_project_report_{}_{}__{}.pdf'.format(
        today.isocalendar()[1], today.year, today.strftime('%d%b%y')
    )

    reports_dir = os.path.join(MEDIA_ROOT, 'reports')

    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)

    filepath = os.path.join(reports_dir, filename)

    pdf_file = open(filepath, 'w')
    pdf_file.write(pdf_contents)
    pdf_file.close()

    slack_utils.upload_file(
        SLACK_STAFF_TOKEN, SLACK_STAFF_REPORTS_CHANNEL, filepath,
        filename=filename,
        initial_comment='<!channel> *Project updates* for *week {}*'.format(
            today.isocalendar()[1])
    )


@job
def notify_weekly_payment_report_slack():
    pdf_contents = weekly_payment_report(render_format='pdf')

    today = datetime.datetime.utcnow()
    filename = 'weekly_payment_report_{}_{}__{}.pdf'.format(
        today.isocalendar()[1], today.year, today.strftime('%d%b%y')
    )

    reports_dir = os.path.join(MEDIA_ROOT, 'reports')

    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)

    filepath = os.path.join(reports_dir, filename)

    pdf_file = open(filepath, 'w')
    pdf_file.write(pdf_contents)
    pdf_file.close()

    slack_utils.upload_file(
        SLACK_STAFF_TOKEN, SLACK_STAFF_REPORTS_CHANNEL, filepath,
        filename=filename,
        initial_comment='<!channel> *Payment updates* for *week {}*'.format(
            today.isocalendar()[1])
    )


@job
def notify_new_user_signup_on_platform(user):
    instance = clean_instance(user, get_user_model())

    slack_msg = '<{}|{}> has joined Tunga'.format(
        '{}/network/{}'.format(TUNGA_URL, instance.user.username),
        instance.user.display_name,
    )

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,

        {

            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_PLATFORM_ALERTS
        }
    )
