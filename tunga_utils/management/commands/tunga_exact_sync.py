###############################################################################
# _*_ coding: utf-8

import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db.models import Q

from tunga_tasks.models import Task, ParticipantPayment
from tunga_tasks.tasks import sync_exact_invoices
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER, STATUS_ACCEPTED, \
    PAYMENT_METHOD_PAYONEER, PAYMENT_METHOD_BANK

TUNGA_API_BASE_URL = 'https://work.tunga.io/api'


def format_money(amount):
    return 'EUR {}'.format(amount)


def get_invoice_url(task_id, invoice_type, developer=None):
    return 'https://work.tunga.io/api/task/{}/download/invoice/?format=pdf&type={}{}'.format(
        task_id, invoice_type, developer and '&developer={}'.format(developer) or ''
    )


def get_task_url(task_id):
    return 'https://work.tunga.io/work/{}/'.format(task_id)


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Tunga Exact Sync
        """
        # command to run: python manage.py tunga_exact_sync

        past_by_2_days = datetime.datetime.utcnow() - relativedelta(days=7)

        tasks = Task.objects.filter(
            (
                (
                    Q(paid=True) |
                    (Q(paid_at__gt=past_by_2_days) | Q(paid_at__isnull=True))
                ) |
                (
                    Q(taskpayment__participantpayment__isnull=False) &
                    Q(taskpayment__participantpayment__created_at__gt=past_by_2_days)
                ) | (
                    Q(taskpayment__isnull=False) &
                    Q(taskpayment__payment_type__in=[
                        PAYMENT_METHOD_PAYONEER, PAYMENT_METHOD_BANK
                    ]) &
                    Q(taskpayment__created_at__gt=past_by_2_days)
                )
            ),
            closed=True
        ).distinct()

        for idx, task in enumerate(tasks):
            if not task.invoice:
                continue
            invoice = task.invoice
            invoice_types = []

            task_owner = task.user
            if task.owner:
                task_owner = task.owner

            developers = []

            admin_emails = ['david@tunga.io', 'bart@tunga.io', 'domieck@tunga.io']

            if invoice.created_at and invoice.created_at.year >= 2018:
                if task.paid and task_owner.type == USER_TYPE_PROJECT_OWNER and task_owner.email not in admin_emails:
                    invoice_types.append('client')

                participation_shares = task.get_participation_shares()
                for share_info in participation_shares:
                    participant = share_info['participant']
                    dev = participant.user

                    if participant.status != STATUS_ACCEPTED or share_info['share'] <= 0:
                        continue

                    if ParticipantPayment.objects.filter(participant=participant):
                        developers.append(dev.id)
                        invoice_types.append('tunga')

                        if invoice.version == 1:
                            invoice_types.append('developer')

                invoice_types = list(set(invoice_types))

            sync_exact_invoices(task, invoice_types=invoice_types, developers=developers)


