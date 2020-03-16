import datetime

from dateutil.relativedelta import relativedelta, MO
from dateutil.rrule import WEEKLY, rrule, MONTHLY
from django.db.models import Q
from django.template.loader import render_to_string
from weasyprint import HTML

from tunga.settings import TUNGA_URL
from tunga_payments.models import Invoice
from tunga_projects.models import ProjectMeta, Project
from tunga_utils.constants import PROJECT_STAGE_ACTIVE, \
    PROGRESS_EVENT_MILESTONE, INVOICE_TYPE_SALE, \
    INVOICE_TYPE_PURCHASE
from tunga_utils.helpers import clean_meta_value


def save_project_metadata(project_id, meta_info):
    if isinstance(meta_info, dict):
        for meta_key in meta_info:
            ProjectMeta.objects.update_or_create(
                project_id=project_id, meta_key=meta_key,
                defaults=dict(meta_value=clean_meta_value(meta_info[meta_key]))
            )


def weekly_project_report(render_format='pdf', weeks_ago=0):
    projects = Project.objects.filter(stage=PROJECT_STAGE_ACTIVE,
                                      archived=False)
    today = datetime.datetime.utcnow()
    week_start = (today - datetime.timedelta(days=today.weekday(),
                                             weeks=weeks_ago)).replace(hour=0,
                                                                       minute=0,
                                                                       second=0,
                                                                       microsecond=0)
    week_end = (week_start + datetime.timedelta(days=6)).replace(hour=23,
                                                                 minute=59,
                                                                 second=59,
                                                                 microsecond=999999)

    report = []
    for project in projects:
        milestones = project.progressevent_set.filter(
            type=PROGRESS_EVENT_MILESTONE, due_at__gte=week_start,
            due_at__lte=week_end
        ).order_by('due_at')
        payments = project.invoice_set.filter(
            (
                Q(type=INVOICE_TYPE_SALE) &
                Q(issued_at__gte=week_start - datetime.timedelta(days=14)) &
                Q(issued_at__lte=week_end - datetime.timedelta(days=14))
                # Client invoices are due 14 days after the issue date
            ) |
            (
                Q(type=INVOICE_TYPE_PURCHASE) &
                Q(issued_at__gte=week_start) &
                Q(issued_at__lte=week_end)
                # Dev invoices are due on the issue date
            )
        ).order_by('issued_at')
        report.append(dict(
            project=dict(
                title=project.title,
                pm=(project.pm or project.user).display_name
            ),
            milestones=milestones,
            payments=[payment for payment in payments if
                      payment.type == INVOICE_TYPE_SALE],
            payouts=[payment for payment in payments if
                     payment.type == INVOICE_TYPE_PURCHASE]
        ))

    ctx = dict(
        week_start=week_start,
        week_end=week_end,
        week_number=week_start.isocalendar()[1],
        projects=report
    )

    html = render_to_string("tunga/pdf/project_report.html",
                            context=ctx).encode(encoding="UTF-8")
    if render_format == 'html':
        return html
    return HTML(string=html, encoding='utf-8').write_pdf()


def weekly_payment_report(render_format='pdf', weeks_ago=0):
    today = datetime.datetime.utcnow()
    week_start = (today - datetime.timedelta(days=today.weekday(),
                                             weeks=weeks_ago)).replace(hour=0,
                                                                       minute=0,
                                                                       second=0,
                                                                       microsecond=0)
    week_end = (week_start + datetime.timedelta(days=6)).replace(hour=23,
                                                                 minute=59,
                                                                 second=59,
                                                                 microsecond=999999)

    non_legacy_invoices = Invoice.objects.exclude(
        Q(project__owner__email='domieck@tunga.io') |
        (
            Q(project__owner__isnull=True) &
            Q(project__user__email='domieck@tunga.io')
        )
    )

    upcoming_this_week = non_legacy_invoices.filter(
        type=INVOICE_TYPE_SALE,
        paid=False,
        issued_at__gte=week_start - datetime.timedelta(days=14),
        issued_at__lte=week_end - datetime.timedelta(days=14),
        # Client invoices are due 14 days after the issue date
    ).order_by('issued_at')

    paid_last_week = non_legacy_invoices.filter(
        type=INVOICE_TYPE_SALE,
        paid=True,
        paid_at__gte=week_start - datetime.timedelta(days=7),
        paid_at__lte=week_end - datetime.timedelta(days=7),
    ).order_by('paid_at')

    overdue = non_legacy_invoices.filter(
        type=INVOICE_TYPE_SALE,
        paid=False,
        issued_at__lte=week_start - datetime.timedelta(days=14),
        # Client invoices are due 14 days after the issue date so don't include those due this week
    ).order_by('issued_at')

    def clean_payments(payments):
        return dict(
            items=[
                dict(
                    id=payment.id,
                    title=payment.title,
                    project=dict(
                        id=payment.project.id,
                        title=payment.project.title,
                        owner=payment.project.owner or payment.project.user,
                        url='{}/projects/{}'.format(TUNGA_URL,
                                                    payment.project.id)
                    ),
                    amount=payment.amount,
                    issued_at=payment.issued_at,
                    due_at=payment.due_at,
                    paid_at=payment.paid_at,
                )
                for payment in payments
            ],
            total=sum([payment.amount for payment in payments])
        )

    ctx = dict(
        week_start=week_start,
        week_end=week_end,
        week_number=week_start.isocalendar()[1],
        paid=clean_payments(paid_last_week),
        overdue=clean_payments(overdue),
        upcoming=clean_payments(upcoming_this_week)
    )

    html = render_to_string("tunga/pdf/payment_report.html",
                            context=ctx).encode(encoding="UTF-8")
    if render_format == 'html':
        return html
    return HTML(string=html, encoding='utf-8').write_pdf()


def get_every_other_monday(date):
    start_of_the_month = date.replace(day=1)
    first_monday = start_of_the_month + relativedelta(weekday=MO(+1))
    list_of_mondays = list(rrule(freq=WEEKLY, count=5, dtstart=first_monday,
                                 bymonth=start_of_the_month.month))
    return list_of_mondays[0::2]
