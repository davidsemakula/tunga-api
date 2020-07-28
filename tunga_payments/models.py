# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import uuid

from actstream.models import Action
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.template.loader import render_to_string
from django.utils.encoding import python_2_unicode_compatible
from dry_rest_permissions.generics import allow_staff_or_superuser
from weasyprint import HTML

from tunga import settings
from tunga.settings import TUNGA_URL
from tunga_projects.models import Project, Participation, ProgressEvent
from tunga_utils.constants import PAYMENT_METHOD_STRIPE, PAYMENT_METHOD_BANK, PAYMENT_METHOD_BITCOIN, \
    PAYMENT_METHOD_BITONIC, INVOICE_TYPE_TUNGA, STATUS_CANCELED, STATUS_APPROVED, STATUS_PENDING, \
    INVOICE_TYPE_CHOICES, CURRENCY_EUR, CURRENCY_CHOICES_EUR_ONLY, \
    INVOICE_TYPE_PURCHASE, PAYMENT_TYPE_PURCHASE, PAYMENT_TYPE_SALE, VAT_LOCATION_WORLD, VAT_LOCATION_EUROPE, \
    VAT_LOCATION_NL, INVOICE_TYPE_SALE, INVOICE_TYPE_CLIENT, INVOICE_PAYMENT_METHOD_CHOICES, STATUS_INITIATED, \
    STATUS_COMPLETED, STATUS_FAILED, STATUS_RETRY, INVOICE_TYPE_CREDIT_NOTA
from tunga_utils.validators import validate_btc_address_or_none


@python_2_unicode_compatible
class Invoice(models.Model):
    status_choices = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_CANCELED, 'Canceled')
    )

    project = models.ForeignKey(to=Project, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    milestone = models.ForeignKey(to=ProgressEvent, blank=True, null=True, on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200, null=True, blank=True)
    type = models.CharField(max_length=50, choices=INVOICE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=17, decimal_places=2)
    currency = models.CharField(max_length=15, choices=CURRENCY_CHOICES_EUR_ONLY, default=CURRENCY_EUR)
    issued_at = models.DateTimeField(default=datetime.datetime.utcnow)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    number = models.CharField(max_length=100, blank=True, null=True)
    processing_fee = models.DecimalField(max_digits=17, decimal_places=2, default=0)
    status = models.CharField(max_length=50, choices=status_choices, null=True, blank=True)
    paid = models.BooleanField(default=False)
    finalized = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    batch_ref = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL, related_name='invoices_created', on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL, related_name='invoices_updated', blank=True, null=True, on_delete=models.DO_NOTHING
    )
    updated_at = models.DateTimeField(auto_now=True)

    last_sent_at = models.DateTimeField(blank=True, null=True)
    last_reminder_at = models.DateTimeField(blank=True, null=True)

    legacy_id = models.CharField(max_length=100, blank=True, null=True)
    migrated_at = models.DateTimeField(blank=True, null=True)

    # Legacy Fields
    payment_method = models.CharField(
        max_length=30, choices=INVOICE_PAYMENT_METHOD_CHOICES,
        blank=True, null=True,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in INVOICE_PAYMENT_METHOD_CHOICES])
    )
    btc_address = models.CharField(max_length=40, validators=[validate_btc_address_or_none], blank=True, null=True)

    activity_objects = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='invoices'
    )

    def __str__(self):
        return "{} | {}".format(self.title, self.user.get_full_name())

    class Meta:
        ordering = ['-issued_at', '-created_at']

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.title:
            self.title = self.project.title
        if not self.status:
            if self.user.is_project_owner and self.type == INVOICE_TYPE_SALE:
                # Only sales invoices being sent to clients are approved by default
                self.status = STATUS_APPROVED
            else:
                self.status = STATUS_PENDING
        if self.id and not self.number:
            self.number = self.generate_invoice_number()
        if not self.id and self.tax_location == VAT_LOCATION_NL:
            # Set NL vat rate
            self.tax_rate = 21
        if self.paid and not self.paid_at:
            self.paid_at = datetime.datetime.utcnow()
        super(Invoice, self).save(force_insert, force_update, using, update_fields)

    @property
    def full_title(self):
        return '{}{}{}'.format(self.project.title, self.project.title != self.title and ': ' or '',
                               self.project.title != self.title and self.title or '')

    @property
    def tax_amount(self):
        return ((self.amount + self.processing_fee) * self.tax_rate) / 100

    @property
    def subtotal(self):
        return self.amount + self.processing_fee

    @property
    def total_amount(self):
        return self.subtotal + self.tax_amount

    def generate_invoice_number(self):
        if self.id and not self.number:
            invoice_number = '{}/{}/P{}/{}'.format(
                (self.created_at or datetime.datetime.utcnow()).strftime('%Y'),
                self.project.owner and self.project.owner.id or self.project.user.id, self.project.id,
                self.id
            )
            if self.type == INVOICE_TYPE_PURCHASE:
                invoice_number = '{}/{}'.format(invoice_number, self.user.id)
            return invoice_number
        return self.number

    @property
    def tax_location(self):
        if self.type in [INVOICE_TYPE_SALE, INVOICE_TYPE_CREDIT_NOTA,
                         INVOICE_TYPE_CLIENT] and self.user and self.user.company and self.user.company.country and self.user.company.country.code:
            client_country = self.user.company.country.code
            if client_country == VAT_LOCATION_NL:
                return VAT_LOCATION_NL
            elif client_country in [
                # EU members
                'BE', 'BG', 'CZ', 'DK', 'DE', 'EE', 'IE', 'EL', 'ES', 'FR', 'HR', 'IT', 'CY', 'LV', 'LT', 'LU',
                'HU', 'MT', 'AT', 'PL', 'PT', 'RO', 'SI', 'SK', 'FI', 'SE', 'UK'
                # European Free Trade Association (EFTA)
                                                                            'IS', 'LI', 'NO', 'CH'
            ]:
                return VAT_LOCATION_EUROPE
        return VAT_LOCATION_WORLD

    @property
    def html(self):
        return render_to_string("tunga/pdf/invoicev3.html", context=dict(invoice=self)).encode(encoding="UTF-8")

    @property
    def pdf(self):
        return HTML(string=self.html, encoding='utf-8').write_pdf()

    @property
    def credit_note_html(self):
        return render_to_string("tunga/pdf/credit_note.html", context=dict(invoice=self)).encode(encoding="UTF-8")

    @property
    def credit_note_pdf(self):
        return HTML(string=self.credit_note_html, encoding='utf-8').write_pdf()

    @property
    def download_url(self):
        return '{}/api/invoices/{}/download/?format=pdf'.format(TUNGA_URL, self.id)

    @property
    def due_at(self):
        if self.type == INVOICE_TYPE_SALE and self.issued_at:
            return (self.issued_at + relativedelta(days=14)).replace(
                hour=23, minute=59, second=59, microsecond=999999)
        elif self.type == INVOICE_TYPE_PURCHASE and self.issued_at:
            return (self.issued_at + relativedelta(days=5)).replace(
                hour=23, minute=59, second=59, microsecond=999999)
        return self.issued_at

    @property
    def is_overdue(self):
        if self.due_at and not self.paid:
            return datetime.datetime.utcnow() > self.due_at
        return False

    @property
    def is_due(self):
        today_end = datetime.datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
        if self.issued_at:
            return self.issued_at <= today_end
        return False

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        allowed_users = [self.user, self.created_by, self.project.user]
        if self.project.owner:
            allowed_users.append(self.project.owner)
        if self.project.pm:
            allowed_users.append(self.project.pm)
        return request.user in allowed_users

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_project_manager or request.user.is_admin

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return self.has_object_read_permission(request)


@python_2_unicode_compatible
class Payment(models.Model):
    payment_method_choices = (
        (PAYMENT_METHOD_STRIPE, 'Stripe'),
        (PAYMENT_METHOD_BANK, 'Bank Transfer'),
        (PAYMENT_METHOD_BITCOIN, 'Bitcoin'),
        (PAYMENT_METHOD_BITONIC, 'Bitonic'),
    )

    status_choices = (
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_RETRY, 'Retry'),
    )

    invoice = models.ForeignKey(to=Invoice, on_delete=models.DO_NOTHING)
    amount = models.IntegerField()
    payment_method = models.CharField(max_length=150, choices=payment_method_choices)
    currency = models.CharField(max_length=15, choices=CURRENCY_CHOICES_EUR_ONLY, default=CURRENCY_EUR)
    status = models.CharField(max_length=50, choices=status_choices, default=STATUS_INITIATED)
    paid_at = models.DateTimeField(blank=True, null=True)
    ref = models.TextField(blank=True, null=True)
    extra = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL, related_name='payments_created',
        blank=True, null=True, on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    legacy_id = models.PositiveIntegerField(blank=True, null=True)
    migrated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return "{}: {} {}".format(self.invoice.title, self.currency, self.amount)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.status == STATUS_COMPLETED and self.invoice and not self.invoice.paid:
            self.invoice.paid = True
            self.invoice.paid_at = self.paid_at or datetime.datetime.now()
            self.invoice.save()
        super(Payment, self).save(
            force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields
        )

    @property
    def type(self):
        if self.invoice.type in [INVOICE_TYPE_TUNGA, INVOICE_TYPE_PURCHASE]:
            return PAYMENT_TYPE_PURCHASE
        else:
            return PAYMENT_TYPE_SALE

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.invoice.has_object_read_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(self):
        return False

    @staticmethod
    @allow_staff_or_superuser
    def has_create_permission(self):
        return False

    @staticmethod
    @allow_staff_or_superuser
    def has_update_permission(self):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return False
