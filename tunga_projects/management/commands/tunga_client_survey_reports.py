import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_payments.models import Invoice
from tunga_projects.models import ProgressEvent
from tunga_utils.constants import INVOICE_TYPE_SALE, \
    PROGRESS_EVENT_DEVELOPER_RATING
from tunga_utils.helpers import create_to_google_sheet_in_platform_updates, \
    save_to_google_sheet


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Schedule progress updates and send update reminders
        """
        # command to run: python manage.py tunga_client_survey_reports

        today = datetime.datetime.utcnow()
        week_ago = today - relativedelta(day=7)
        # invoices = Invoice.objects.filter(type=INVOICE_TYPE_SALE)
        client_surveys = ProgressEvent.objects.filter(
            type=PROGRESS_EVENT_DEVELOPER_RATING,
            created_at__range=(week_ago, today)
        )
        total_count = client_surveys.count()

        title = "Client Survey Report - %s" % (today.strftime("%B %Y"))
        file_id = create_to_google_sheet_in_platform_updates(title)
        missed = 0
        filled = 0

        for client_survey in client_surveys:
            # print client_survey
            sheet_data = [str(client_survey.created_at),
                          str(client_survey.project.title),
                          str(client_survey.status).title()]
            if client_survey.status == 'missed':
                missed = missed + 1
            elif client_survey.status == 'completed':
                filled = filled + 1
            print(sheet_data)
            print(total_count)
            save_to_google_sheet(file_id, sheet_data)

        percentage_filled = (filled / total_count) * 100

        save_to_google_sheet(file_id, ["", "Total Client Surveys", total_count],
                             total_count + 1)
        save_to_google_sheet(file_id, ["", "Total Filled Surveys", filled],
                             total_count + 2)
        save_to_google_sheet(file_id, ["", "Total Missed Surveys", missed],
                             total_count + 3)
        save_to_google_sheet(file_id,
                             ["", "Percentage Filled",
                              str(percentage_filled) + "%"],
                             total_count + 4)

        sheet_data = ['Date Created', 'Project', 'Status']
        save_to_google_sheet(file_id, sheet_data)
