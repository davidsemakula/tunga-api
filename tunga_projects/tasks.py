from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q
from django_rq.decorators import job

from tunga_projects.models import Project, InterestPoll, Participation
from tunga_projects.notifications.email import notify_interest_poll_email
from tunga_projects.notifications.slack import notify_project_slack_dev
from tunga_utils import exact_utils
from tunga_utils.constants import PROJECT_STAGE_OPPORTUNITY, \
    USER_TYPE_DEVELOPER, STATUS_INTERESTED, STATUS_ACCEPTED, INVOICE_TYPE_SALE, \
    INVOICE_TYPE_PURCHASE, PROJECT_CATEGORY_PROJECT, PROJECT_CATEGORY_DEDICATED, \
    STATUS_APPROVED
from tunga_utils.helpers import clean_instance
from tunga_utils.hubspot_utils import create_or_update_project_hubspot_deal


@job
def sync_hubspot_deal(project, **kwargs):
    project = clean_instance(project, Project)
    create_or_update_project_hubspot_deal(project, **kwargs)


@job
def activate_project(project):
    project = clean_instance(project, Project)

    approved_polls = project.interestpoll_set.filter(status=STATUS_INTERESTED,
                                                     approval_status=STATUS_ACCEPTED)
    for poll in approved_polls:
        Participation.objects.update_or_create(
            project=project, user=poll.user,
            defaults=dict(
                status=STATUS_ACCEPTED,
                responded_at=poll.responded_at,
                created_by=poll.created_by or poll.project.user
            )
        )


@job
def manage_interest_polls(project, remind=False):
    project = clean_instance(project, Project)

    if project.stage != PROJECT_STAGE_OPPORTUNITY:
        # Only poll dev interest for opportunities
        return

    if remind:
        notify_project_slack_dev.delay(project.id, reminder=True)

    developers = get_user_model().objects.filter(is_active=True,
                                                 type=USER_TYPE_DEVELOPER,
                                                 userprofile__skills__in=project.skills.all())

    for developer in developers:
        interest_poll, created = InterestPoll.objects.update_or_create(
            project=project, user=developer,
            defaults=dict(created_by=project.user)
        )

        if created:
            notify_interest_poll_email.delay(interest_poll.id,
                                             reminder=False)
        elif remind:
            notify_interest_poll_email.delay(interest_poll.id,
                                             reminder=True)


@job
def complete_exact_sync(project, **kwargs):
    project = clean_instance(project, Project)

    if project.archived and project.category:
        margin_ratio = Decimal(0)
        if project.category == PROJECT_CATEGORY_PROJECT:
            margin_ratio = Decimal('0.4')
        elif project.category == PROJECT_CATEGORY_DEDICATED:
            margin_ratio = Decimal('0.5')

        total_margin = Decimal(0)
        total_dev = Decimal(0)

        # Upload all project invoices
        invoices = project.invoice_set.filter(
            (
                Q(finalized=True) & Q(type=INVOICE_TYPE_SALE)
            ) |
            (
                Q(status=STATUS_APPROVED) & Q(type=INVOICE_TYPE_PURCHASE)
            ) |
            (
                Q(paid=True) &
                Q(type__in=[INVOICE_TYPE_SALE, INVOICE_TYPE_PURCHASE])
            )
        )
        for invoice in invoices:
            exact_utils.upload_invoice_v3(invoice)

            if margin_ratio:
                if invoice.type == INVOICE_TYPE_SALE:
                    total_margin += Decimal(margin_ratio * invoice.subtotal)
                elif invoice.type == INVOICE_TYPE_PURCHASE:
                    total_dev += invoice.subtotal

        # Create project
        exact_utils.create_project_entry_v3(project, total_dev - total_margin)
