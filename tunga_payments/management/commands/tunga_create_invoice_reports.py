import datetime

from django.core.management.base import BaseCommand

from tunga_payments.models import Invoice
from tunga_utils.constants import INVOICE_TYPE_SALE
from tunga_utils.helpers import create_to_google_sheet_in_platform_updates, \
    save_to_google_sheet


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Schedule progress updates and send update reminders
        """
        # command to run: python manage.py tunga_create_invoice_reports

        today = datetime.datetime.utcnow()

        # invoices = Invoice.objects.filter(type=INVOICE_TYPE_SALE)
        invoices = Invoice.objects.filter(type=INVOICE_TYPE_SALE,
                                          finalized=True,
                                          created_at__year=today.year,
                                          created_at__month=today.month)

        title = "Client Invoices - %s" % (today.strftime("%B %Y"))
        file_id = create_to_google_sheet_in_platform_updates(title)

        for invoice in invoices:
            sheet_data = [str(invoice.created_at), str(invoice.number),
                          int(invoice.amount), str(invoice.full_title),
                          str(invoice.project.title),
                          str(invoice.project.owner.display_name.encode(
                              'utf-8').strip())]
            save_to_google_sheet(file_id, sheet_data)

        sheet_data = ['Date Created', 'Invoice Number',
                      'Amount', 'Invoice Name',
                      'Project Name', 'Project Owner']
        save_to_google_sheet(file_id, sheet_data)
