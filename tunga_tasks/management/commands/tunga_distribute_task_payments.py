import datetime

from django.core.management.base import BaseCommand

from tunga_tasks.models import Task
from tunga_tasks.tasks import distribute_task_payment_payoneer


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Distribute task payments.
        """
        # command to run: python manage.py tunga_distribute_task_payments

        utc_now = datetime.datetime.utcnow()
        # min_date = utc_now - relativedelta(minutes=1)

        # Distribute payments for tasks which have been paid and marked for distribution
        tasks = Task.objects.filter(
            closed=True, payment_approved=True,
            distribution_approved=True, pay_distributed=False,
            # paid=True, paid_at__lte=min_date
        )
        for task in tasks:
            distribute_task_payment_payoneer.delay(task.id)
