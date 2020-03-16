import base64

import datetime
from django.utils.dateformat import DateFormat
from django_rq import job

from tunga.settings import TUNGA_URL, MANDRILL_VAR_FIRST_NAME
from tunga_payments.models import Invoice
from tunga_utils import mandrill_utils
from tunga_utils.constants import INVOICE_TYPE_SALE, INVOICE_TYPE_PURCHASE
from tunga_utils.helpers import clean_instance


@job
def notify_invoice_email(invoice, updated=False):
    invoice = clean_instance(invoice, Invoice)
    if invoice.type == INVOICE_TYPE_SALE:
        if updated:
            notify_updated_invoice_email_client(invoice)
        else:
            notify_new_invoice_email_client(invoice)
    elif invoice.type == INVOICE_TYPE_PURCHASE and not updated:
        notify_new_invoice_email_dev(invoice)


@job
def notify_new_invoice_email_client(invoice):
    invoice = clean_instance(invoice, Invoice)

    today_end = datetime.datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)

    if (not invoice.legacy_id) and invoice.type == INVOICE_TYPE_SALE and \
        invoice.issued_at <= today_end and not invoice.last_sent_at and not invoice.paid:

        # only notify about non-legacy client invoices that are already due and haven't been sent yet

        invoice_user_email = invoice.user.invoice_email or invoice.user.email
        to = [invoice_user_email]
        if invoice.project.owner:
            invoice_owner_email = invoice.project.owner.invoice_email or invoice.project.owner.email
            if invoice_owner_email != invoice_user_email:
                to.append(invoice_owner_email)

        if invoice.project.user:
            project_user_email = invoice.project.user.invoice_email or invoice.project.user.email
            if project_user_email != invoice_user_email:
                to.append(project_user_email)

        payment_link = '{}/projects/{}/pay'.format(TUNGA_URL, invoice.project.id)

        merge_vars = [
            mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, invoice.user.first_name),
            mandrill_utils.create_merge_var('project_title', invoice.full_title),
            mandrill_utils.create_merge_var('payment_link', payment_link),
        ]

        pdf_file_contents = base64.b64encode(invoice.pdf)

        attachments = [
            dict(
                content=pdf_file_contents,
                name='Invoice - {}.pdf'.format(invoice.full_title),
                type='application/pdf'
            )
        ]

        mandrill_response = mandrill_utils.send_email('105-client-invoice-is-ready', to, merge_vars=merge_vars, attachments=attachments)
        if mandrill_response:
            invoice.last_sent_at = datetime.datetime.utcnow()
            invoice.save()

            mandrill_utils.log_emails.delay(mandrill_response, to)


@job
def notify_updated_invoice_email_client(invoice):
    invoice = clean_instance(invoice, Invoice)

    today_end = datetime.datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)

    if (not invoice.legacy_id) and invoice.type == INVOICE_TYPE_SALE and \
        invoice.issued_at <= today_end and invoice.last_sent_at and not invoice.paid:
        # only notify updates to non-legacy client invoices that are already due and have been sent before

        invoice_user_email = invoice.user.invoice_email or invoice.user.email
        to = [invoice_user_email]
        if invoice.project.owner:
            invoice_owner_email = invoice.project.owner.invoice_email or invoice.project.owner.email
            if invoice_owner_email != invoice_user_email:
                to.append(invoice_owner_email)

        if invoice.project.user:
            project_user_email = invoice.project.user.invoice_email or invoice.project.user.email
            if project_user_email != invoice_user_email:
                to.append(project_user_email)

        payment_link = '{}/projects/{}/pay'.format(TUNGA_URL, invoice.project.id)

        merge_vars = [
            mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, invoice.user.first_name),
            mandrill_utils.create_merge_var('invoice_title', invoice.full_title),
            mandrill_utils.create_merge_var('payment_link', payment_link),
        ]

        pdf_file_contents = base64.b64encode(invoice.credit_note_pdf)

        attachments = [
            dict(
                content=pdf_file_contents,
                name='Credit note for Invoice - {}.pdf'.format(invoice.full_title),
                type='application/pdf'
            )
        ]

        mandrill_response = mandrill_utils.send_email('109-client-credit-note', to, merge_vars=merge_vars, attachments=attachments)
        if mandrill_response:
            invoice.last_sent_at = datetime.datetime.utcnow()
            invoice.save()

            mandrill_utils.log_emails.delay(mandrill_response, to)


@job
def notify_new_invoice_email_dev(invoice):
    invoice = clean_instance(invoice, Invoice)

    if invoice.legacy_id or invoice.type != INVOICE_TYPE_PURCHASE:
        # ignore legacy invoices and only notify about developer invoices
        return

    to = [invoice.user.email]

    merge_vars = [
        mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, invoice.user.first_name),
        mandrill_utils.create_merge_var('payout_title', invoice.full_title),
        mandrill_utils.create_merge_var('payout_date', DateFormat(invoice.issued_at).format('l, jS F, Y')),
    ]

    mandrill_utils.send_email('107-payout-update', to, merge_vars=merge_vars)


@job
def notify_paid_invoice_email(invoice):
    invoice = clean_instance(invoice, Invoice)
    if invoice.type == INVOICE_TYPE_PURCHASE:
        notify_paid_invoice_email_dev(invoice)


@job
def notify_paid_invoice_email_dev(invoice):
    invoice = clean_instance(invoice, Invoice)

    if invoice.legacy_id or invoice.type != INVOICE_TYPE_PURCHASE or not invoice.paid:
        # ignore legacy invoices and only notify about developer invoices
        return

    to = [invoice.user.email]

    merge_vars = [
        mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, invoice.user.first_name),
        mandrill_utils.create_merge_var('payout_title', invoice.full_title),
    ]

    pdf_file_contents = base64.b64encode(invoice.pdf)

    attachments = [
        dict(
            content=pdf_file_contents,
            name='Invoice - {}.pdf'.format(invoice.full_title),
            type='application/pdf'
        )
    ]

    mandrill_utils.send_email('108-payout-made', to, merge_vars=merge_vars, attachments=attachments)
