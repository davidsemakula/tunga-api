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
        file_id = '1_-SxkrrPk8uqwbz_Xe2sZurff9tYCN0sqTkVGJZDNS4'

        for client_survey in client_surveys:
            # print client_survey
            sheet_data = [str(client_survey.created_at),
                          str(client_survey.project.title),
                          str(client_survey.status).title()]
            print(sheet_data)
            print(total_count)
            save_to_google_sheet(file_id, sheet_data,index=2)
