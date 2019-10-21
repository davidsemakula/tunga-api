import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db.models import Q

from tunga_payments.models import Invoice
from tunga_projects.models import Project
from tunga_projects.tasks import complete_exact_sync
from tunga_utils.constants import INVOICE_TYPE_SALE, INVOICE_TYPE_PURCHASE, \
    PROJECT_CATEGORY_DEDICATED, PROJECT_CATEGORY_PROJECT, PROJECT_CATEGORY_OTHER
from tunga_utils.exact_utils import upload_invoice_v3


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Schedule progress updates and send update reminders
        """
        # command to run: python manage.py tunga_sync_invoices_exact

        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        past_by_48_hours = today_start - relativedelta(hours=48)

        invoices = Invoice.objects.filter(
            (
                (
                    Q(paid=True) & Q(paid_at__gte=past_by_48_hours) &
                    Q(project__category__isnull=True) &
                    Q(type__in=[INVOICE_TYPE_SALE, INVOICE_TYPE_PURCHASE])
                ) | (
                    Q(finalized=True) & Q(updated_at__gte=past_by_48_hours) &
                    Q(project__category__in=[
                        PROJECT_CATEGORY_PROJECT,
                        PROJECT_CATEGORY_DEDICATED,
                        PROJECT_CATEGORY_OTHER
                    ]) & Q(type=INVOICE_TYPE_SALE)
                )
            ),
            legacy_id__isnull=True
        )

        for invoice in invoices:
            upload_invoice_v3(invoice)

        projects = Project.objects.filter(
            archived=True,
            category__in=[
                PROJECT_CATEGORY_PROJECT,
                PROJECT_CATEGORY_DEDICATED,
                PROJECT_CATEGORY_OTHER
            ],
            archived_at__gte=past_by_48_hours
        )

        for project in projects:
            complete_exact_sync(project)
