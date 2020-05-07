import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_projects.models import ProgressEvent
from tunga_utils.constants import PROGRESS_EVENT_DEVELOPER_RATING, \
    PROJECT_CATEGORY_PROJECT, PROJECT_CATEGORY_DEDICATED, \
    PROJECT_STAGE_ACTIVE
from tunga_utils.helpers import save_to_google_sheet


def get_dedicated_surveys(dedicated_client_surveys):
    dedicated_reports = []
    for dedicated_client_survey in dedicated_client_surveys:
        if dedicated_client_survey.status == 'missed':
            sheet_data = [str(dedicated_client_survey.created_at),
                          str(dedicated_client_survey.project.title),
                          str(
                              dedicated_client_survey.project.category).title(),
                          str(dedicated_client_survey.status).title(),
                          ]
            dedicated_reports.append(sheet_data)
        elif dedicated_client_survey.status == 'completed':
            developer_ratings = dedicated_client_survey.developerrating_set.all()
            for developer_rating in developer_ratings:
                sheet_data = [str(dedicated_client_survey.created_at),
                              str(dedicated_client_survey.project.title),
                              str(
                                  dedicated_client_survey.project.category).title(),
                              str(dedicated_client_survey.status).title(),
                              developer_rating.rating,
                              str(developer_rating.user.display_name),
                              ]
                dedicated_reports.append(sheet_data)
    return dedicated_reports


def get_project_surveys(project_client_surveys):
    project_reports = []
    for project_client_survey in project_client_surveys:
        if project_client_survey.status == 'missed':
            sheet_data = [str(project_client_survey.created_at),
                          str(project_client_survey.project.title),
                          str(
                              project_client_survey.project.category).title(),
                          str(project_client_survey.status).title(),
                          ]
            project_reports.append(sheet_data)
        elif project_client_survey.status == 'completed':
            sheet_data = [str(project_client_survey.created_at),
                          str(project_client_survey.project.title),
                          str(
                              project_client_survey.project.category).title(),
                          str(project_client_survey.status).title(),
                          project_client_survey.progressreport_set.last().rate_communication,
                          ]
            project_reports.append(sheet_data)
    return project_reports


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Schedule progress updates and send update reminders
        """
        # command to run: python manage.py tunga_client_survey_reports
        today_start = datetime.datetime.utcnow()
        weekday = today_start.weekday()
        week_number = today_start.isocalendar()[1]

        if weekday == 5 and (week_number % 2 == 1):
            today = datetime.datetime.utcnow()
            week_ago = today - relativedelta(days=7)
            project_client_surveys = ProgressEvent.objects.filter(
                type=PROGRESS_EVENT_DEVELOPER_RATING,
                project__category=PROJECT_CATEGORY_PROJECT,
                project__stage=PROJECT_STAGE_ACTIVE,
                created_at__range=[week_ago, today]
            )
            print("Number of project surveys: %s" % project_client_surveys.count())

            dedicated_client_surveys = ProgressEvent.objects.filter(
                type=PROGRESS_EVENT_DEVELOPER_RATING,
                project__category=PROJECT_CATEGORY_DEDICATED,
                project__stage=PROJECT_STAGE_ACTIVE,
                created_at__range=[week_ago, today]
            )
            print("Number of dedicated surveys: %s" % dedicated_client_surveys.count())

            title = "Client Survey Report - %s" % (today.strftime("%B %Y"))
            file_id = '1_-SxkrrPk8uqwbz_Xe2sZurff9tYCN0sqTkVGJZDNS4'

            project_reports = get_project_surveys(
                project_client_surveys)
            dedicated_reports = get_dedicated_surveys(dedicated_client_surveys)
            project_reports.extend(dedicated_reports)
            print("Number of total reports: %s" % len(project_reports))
            for project_report in project_reports:
                save_to_google_sheet(file_id, project_report, index=2)
