import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_auth.models import TungaUser
from tunga_payments.models import Invoice
from tunga_projects.models import ProgressEvent, Project, Participation, \
    DeveloperRating
from tunga_utils.constants import INVOICE_TYPE_SALE, \
    PROGRESS_EVENT_DEVELOPER_RATING
from tunga_utils.helpers import create_to_google_sheet_in_platform_updates, \
    save_to_google_sheet


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Schedule progress updates and send update reminders
        """
        # command to run: python manage.py tunga_developer_rating_report

        today = datetime.datetime.utcnow()
        active_projects = Project.objects.filter(archived=False).values_list(
            'id', flat=True)
        active_projects = list(active_projects)

        active_developers = Participation.objects.filter(
            project__id__in=active_projects).values_list('user__id', flat=True)
        active_developers = list(active_developers)
        active_developers = TungaUser.objects.filter(id__in=active_developers)

        title = "Developer Rating - %s" % (today.strftime("%B %Y"))
        file_id = create_to_google_sheet_in_platform_updates(title)
        print("Number of active devs: %s" % active_developers.count())
        for developer in active_developers:
            sheet_data = [str(developer.display_name),
                          str(developer.average_rating)]
            save_to_google_sheet(file_id, sheet_data, index=2)
        heading_sheet_data = ['Developer', 'Rating']
        save_to_google_sheet(file_id, heading_sheet_data)
