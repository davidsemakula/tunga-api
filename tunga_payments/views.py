# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import csv
import datetime
# Create your views here.
import json
import uuid
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import redirect
from dry_rest_permissions.generics import DRYPermissions
from rest_framework import status
from rest_framework.decorators import list_route, detail_route
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.renderers import StaticHTMLRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.viewsets import ModelViewSet
from six.moves.urllib_parse import urlencode, quote_plus
# from stripe import InvalidRequestError

from tunga_payments.filterbackends import InvoiceFilterBackend, \
    PaymentFilterBackend
from tunga_payments.filters import InvoiceFilter, PaymentFilter
from tunga_payments.models import Invoice, Payment
from tunga_payments.notifications.generic import notify_paid_invoice, \
    notify_invoice
from tunga_payments.serializers import InvoiceSerializer, PaymentSerializer, \
    StripePaymentSerializer, \
    BulkInvoiceSerializer, StripePaymentIntentSerializer, \
    StripePaymentIntentCompleteSerializer, ExportInvoiceSerializer
from tunga_tasks.renderers import PDFRenderer
from tunga_utils import stripe_utils
from tunga_utils.constants import PAYMENT_METHOD_STRIPE, CURRENCY_EUR, \
    STATUS_COMPLETED, INVOICE_TYPE_CREDIT_NOTA, \
    INVOICE_TYPE_PURCHASE, INVOICE_TYPE_SALE
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_utils.pagination import LargeResultsSetPagination


class InvoiceViewSet(ModelViewSet):
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.filter(archived=False)
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = InvoiceFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (InvoiceFilterBackend,)
    pagination_class = LargeResultsSetPagination
    search_fields = ('title', '^project__title')

    def update(self, request, *args, **kwargs):
        return super(InvoiceViewSet, self).update(request, *args, **kwargs)

    @list_route(methods=['post'],
                permission_classes=[IsAuthenticated, DRYPermissions],
                url_path='bulk', url_name='bulk-create-invoices')
    def create_bulk_invoices(self, request):
        group_batch_ref = uuid.uuid4()
        for list_invoices in request.data:
            serializer = InvoiceSerializer(data=list_invoices,
                                           context={'request': request})
            if serializer.is_valid():
                invoice = serializer.save(batch_ref=group_batch_ref)
                if invoice.type == INVOICE_TYPE_PURCHASE:
                    invoice.generate_invoice_number()
                    invoice.save()
        results = Invoice.objects.filter(batch_ref=group_batch_ref)
        output_serializer = InvoiceSerializer(results, many=True)
        data = output_serializer.data[:]
        return Response(data, status=status.HTTP_201_CREATED)

    @list_route(methods=['put'],
                permission_classes=[IsAuthenticated, DRYPermissions],
                serializer_class=BulkInvoiceSerializer,
                url_path='bulk/(?P<batch_ref>[0-9a-f-]+)',
                url_name='bulk-put-invoices')
    def create_put_invoices(self, request, batch_ref=None):
        ids_updated = []
        invoices = Invoice.objects.filter(batch_ref=batch_ref)
        if invoices:
            request_project = request.data.get('project', None)
            request_invoices = request.data.get('invoices', None)
            request_title = request.data.get('title', None)
            request_milestone = request.data.get('milestone', None)
            batch_title = invoices.first().title
            batch_milestone = invoices.first().milestone.id
            batch_project = invoices.first().project.id
            if (batch_title == request_title) and (
                batch_milestone == request_milestone.get('id', None)) \
                and (batch_project == request_project.get('id', None)):
                for invoice in request_invoices:
                    if 'id' in invoice:
                        id_ = invoice.pop('id', None)
                        ids_updated.append(id_)
                        created = Invoice.objects.get(id=id_,
                                                      batch_ref=batch_ref)  # .update(**invoice)
                        serializer = InvoiceSerializer(created, data=invoice,
                                                       partial=True)
                        if serializer.is_valid():
                            serializer.save()

                    else:
                        serializer = InvoiceSerializer(data=invoice, context={
                            'request': request})
                        if serializer.is_valid():
                            serializer.save(batch_ref=batch_ref)
                invoices_ids = list(invoices.values_list('id', flat=True))
                ids_to_delete = list(set(invoices_ids) - set(invoices_ids))
                Invoice.objects.filter(id__in=ids_to_delete).delete()
                results = Invoice.objects.filter(batch_ref=batch_ref)
                output_serializer = InvoiceSerializer(results, many=True)
                data = output_serializer.data[:]
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response(
                    dict(message='Invoice data in batch does not match'),
                    status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(
                dict(message='No Invoices with that batch ref exist'),
                status=status.HTTP_404_NOT_FOUND)

    @list_route(methods=['delete'],
                permission_classes=[IsAuthenticated, DRYPermissions],
                url_path='bulk/(?P<batch_ref>[0-9a-f-]+)',
                url_name='bulk-delete-invoices')
    def delete_bulk_invoices(self, request, batch_ref=None):
        Invoice.objects.filter(batch_ref=batch_ref).delete()
        return Response({}, status=status.HTTP_200_OK)

    @detail_route(
        methods=['get'], url_path='download',
        renderer_classes=[PDFRenderer, StaticHTMLRenderer],
        permission_classes=[AllowAny]
    )
    def download_invoice(self, request, pk=None):
        """
        Download Invoice Endpoint
        ---
        omit_serializer: True
        omit_parameters:
            - query
        """
        current_url = '{}?{}'.format(
            reverse(request.resolver_match.url_name, kwargs={'pk': pk}),
            urlencode(request.query_params)
        )
        login_url = '/signin?next=%s' % quote_plus(current_url)
        if not request.user.is_authenticated():
            return redirect(login_url)

        invoice = get_object_or_404(self.get_queryset(), pk=pk)
        if invoice:
            try:
                self.check_object_permissions(request, invoice)
            except NotAuthenticated:
                return redirect(login_url)
            except PermissionDenied:
                return HttpResponse(
                    "You do not have permission to access this invoice")

            is_project_manager_on_project = request.user == invoice.project.pm
            is_developer_on_project = request.user in invoice.project.participants.all() and invoice.type == INVOICE_TYPE_PURCHASE
            is_client_on_project = request.user == invoice.project.owner and (
                invoice.type in [INVOICE_TYPE_SALE,
                                 INVOICE_TYPE_CREDIT_NOTA])

            if not (
                request.user.is_admin or is_client_on_project or is_project_manager_on_project or is_developer_on_project):
                return HttpResponse(
                    "You do not have permission to access this invoice")

        if request.accepted_renderer.format == 'html':
            if invoice.type == INVOICE_TYPE_CREDIT_NOTA:
                return HttpResponse(invoice.credit_note_html)
            return HttpResponse(invoice.html)
        else:
            if invoice.type == INVOICE_TYPE_CREDIT_NOTA:
                http_response = HttpResponse(invoice.credit_note_pdf,
                                             content_type='application/pdf')
                http_response[
                    'Content-Disposition'] = 'filename="Invoice_{}_{}_{}.pdf"'.format(
                    invoice and invoice.number or pk,
                    invoice and invoice.project and invoice.project.title or pk,
                    invoice and invoice.title or pk
                )
                return http_response
            else:
                http_response = HttpResponse(invoice.pdf,
                                             content_type='application/pdf')
                http_response[
                    'Content-Disposition'] = 'filename="Invoice_{}_{}_{}.pdf"'.format(
                    invoice and invoice.number or pk,
                    invoice and invoice.project and invoice.project.title or pk,
                    invoice and invoice.title or pk
                )
                return http_response

    @detail_route(methods=['post'],
                  permission_classes=[IsAuthenticated, DRYPermissions],
                  url_path='archive', url_name='archive-unpaid-invoices')
    def archive_invoice(self, request, pk=None):
        """
            Invoice Payment Endpoint
            ---
            omit_serializer: true
            omit_parameters: false
                - query
        """
        invoice = self.get_object()
        if not invoice.paid:
            invoice.archived = True
            invoice.save()
            return Response(dict(message='Invoice has been archived'),
                            status=status.HTTP_201_CREATED)
        else:
            return Response(dict(message='Invoice has been already paid'),
                            status=status.HTTP_200_OK)

    @detail_route(methods=['post'],
                  permission_classes=[IsAuthenticated, DRYPermissions],
                  url_path='generate', url_name='generate-invoice')
    def generate_invoice(self, request, pk=None):
        """
            Invoice Generate Endpoint
            ---
            omit_serializer: true
            omit_parameters: false
                - query
        """
        invoice = self.get_object()
        if not invoice.finalized:
            invoice.finalized = True
            invoice.save()
            if not invoice.number:
                # generate and save invoice number
                invoice_number = invoice.generate_invoice_number()
                invoice.number = invoice_number
                Invoice.objects.filter(id=invoice.id).update(
                    number=invoice_number,
                    user=invoice.project.owner or invoice.project.user)
                notify_invoice.delay(invoice.id, updated=False)
            invoice_serializer = InvoiceSerializer(invoice,
                                                   context={'request': request})
            return Response(invoice_serializer.data,
                            status=status.HTTP_201_CREATED)
        else:
            invoice_serializer = InvoiceSerializer(invoice,
                                                   context={'request': request})
            return Response(invoice_serializer.data, status=status.HTTP_200_OK)

    @list_route(methods=['post'],
                permission_classes=[IsAuthenticated],
                serializer_class=ExportInvoiceSerializer,
                url_path='export', url_name='export-invoice')
    def export_invoices(self, request, pk=None):
        """
            Invoice Generate Endpoint
            ---
            omit_serializer: true
            omit_parameters: false
                - query
        """
        serializer = ExportInvoiceSerializer(data=request.data)
        if serializer.is_valid():
            start = serializer.validated_data['start']
            end = serializer.validated_data['end']
            type = serializer.validated_data['type']

            invoices = Invoice.objects.filter(created_at__range=(start, end),
                                              type=type)
            response = HttpResponse(content_type='text/csv')
            filename = "%s-invoices-export-%s-%s.csv" % (
                type, start.strftime('%m/%d/%Y'), end.strftime('%m/%d/%Y'))
            response[
                'Content-Disposition'] = "attachment; filename=%s" % filename

            writer = csv.writer(response)
            writer.writerow(
                ['client', 'project', 'description', 'invoice_number', 'amount',
                 'date', 'due_date', 'paid'])
            [writer.writerow([
                invoice.project.owner.company, invoice.project.title,
                invoice.title, invoice.number, invoice.amount,
                invoice.created_at,
                invoice.due_at, invoice.paid]) for invoice in
                invoices]
            return response
        return Response({})


class PaymentViewSet(ModelViewSet):
    serializer_class = PaymentSerializer
    queryset = Payment.objects.filter(invoice__archived=False)
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = PaymentFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (PaymentFilterBackend,)
