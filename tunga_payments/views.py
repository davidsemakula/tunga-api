# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
# Create your views here.
import json
import uuid
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import redirect
from dry_rest_permissions.generics import DRYPermissions, DRYObjectPermissions
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
from stripe import InvalidRequestError

from tunga_payments.filterbackends import InvoiceFilterBackend, PaymentFilterBackend
from tunga_payments.filters import InvoiceFilter, PaymentFilter
from tunga_payments.models import Invoice, Payment
from tunga_payments.serializers import InvoiceSerializer, PaymentSerializer, StripePaymentSerializer, \
    BulkInvoiceSerializer
from tunga_tasks.renderers import PDFRenderer
from tunga_utils import stripe_utils
from tunga_utils.constants import PAYMENT_METHOD_STRIPE, CURRENCY_EUR, STATUS_COMPLETED
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class InvoiceViewSet(ModelViewSet):
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all()
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = InvoiceFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (InvoiceFilterBackend,)

    @list_route(methods=['post'], permission_classes=[IsAuthenticated, DRYPermissions],
                url_path='bulk', url_name='bulk-create-invoices')
    def create_bulk_invoices(self, request):
        group_batch_ref = uuid.uuid4()
        for list_invoices in request.data:
            print(request.data)
            serializer = InvoiceSerializer(data=list_invoices, context={'request': request})
            if serializer.is_valid():
                serializer.save(batch_ref=group_batch_ref)
        results = Invoice.objects.filter(batch_ref=group_batch_ref)
        output_serializer = InvoiceSerializer(results, many=True)
        data = output_serializer.data[:]
        return Response(data, status=status.HTTP_201_CREATED)

    @list_route(methods=['put'], permission_classes=[IsAuthenticated, DRYPermissions],
                serializer_class=BulkInvoiceSerializer,
                url_path='bulk/(?P<batch_ref>[0-9a-f-]+)', url_name='bulk-put-invoices')
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
            if (batch_title == request_title) and (batch_milestone == request_milestone.get('id', None)) \
                and (batch_project == request_project.get('id', None)):
                for invoice in request_invoices:
                    if 'id' in invoice:
                        id_ = invoice.pop('id', None)
                        ids_updated.append(id_)
                        created = Invoice.objects.get(id=id_, batch_ref=batch_ref)  # .update(**invoice)
                        serializer = InvoiceSerializer(created, data=invoice, partial=True)
                        if serializer.is_valid():
                            serializer.save()

                    else:
                        serializer = InvoiceSerializer(data=invoice, context={'request': request})
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
                return Response(dict(message='Invoice data in batch does not match'),
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(dict(message='No Invoices with that batch ref exist'),
                            status=status.HTTP_404_NOT_FOUND)

    @list_route(methods=['delete'], permission_classes=[IsAuthenticated, DRYPermissions],
                url_path='bulk/(?P<batch_ref>[0-9a-f-]+)', url_name='bulk-delete-invoices')
    def delete_bulk_invoices(self, request, batch_ref=None):
        Invoice.objects.filter(batch_ref=batch_ref).delete()
        return Response({}, status=status.HTTP_200_OK)

    @detail_route(
        methods=['get', 'post'], url_path='pay', url_name='pay-invoice',
        serializer_class=StripePaymentSerializer,
        permission_classes=[IsAuthenticated]
    )
    def pay(self, request, pk=None):
        """
        Invoice Payment Endpoint
        ---
        omit_serializer: true
        omit_parameters:
            - query
        """
        invoice = self.get_object()
        payload = request.data

        if payload['payment_method'] == PAYMENT_METHOD_STRIPE:
            # Pay with Stripe
            paid_at = datetime.datetime.utcnow()

            stripe = stripe_utils.get_client()

            try:
                # Create customer
                customer = stripe.Customer.create(**dict(source=payload['token'], email=payload['email']))

                # Create Charge
                charge = stripe.Charge.create(
                    idempotency_key=payload.get('idem_key', None),
                    **dict(
                        amount=payload['amount'],
                        description=payload.get('description', invoice.title),
                        currency=payload.get('currency', CURRENCY_EUR),
                        customer=customer.id,
                        metadata=dict(
                            invoice_id=invoice.id,
                            project_id=invoice.project.id
                        )
                    )
                )

                if charge.paid:
                    # Save payment details
                    Payment.objects.create(
                        invoice=invoice,
                        payment_method=PAYMENT_METHOD_STRIPE,
                        amount=Decimal(charge.amount) * Decimal(0.01),
                        currency=(charge.currency or CURRENCY_EUR).upper(),
                        status=STATUS_COMPLETED,
                        ref=charge.id,
                        paid_at=paid_at,
                        created_by=request.user,
                        extra=json.dumps(dict(
                            paid=charge.paid,
                            token=payload['token'],
                            email=payload['email'],
                            captured=charge.captured,
                        ))
                    )

                    # Update invoice
                    invoice.paid = True
                    invoice.paid_at = paid_at
                    invoice.save()

                invoice_serializer = InvoiceSerializer(invoice, context={'request': request})
                return Response(invoice_serializer.data)
            except InvalidRequestError:
                return Response(dict(message='We could not process your payment! Please contact hello@tunga.io'),
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(dict(message='We could not process your payment! Please contact hello@tunga.io'),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                return HttpResponse("You do not have permission to access this invoice")

        if request.accepted_renderer.format == 'html':
            return HttpResponse(invoice.html)
        else:
            http_response = HttpResponse(invoice.pdf, content_type='application/pdf')
            http_response['Content-Disposition'] = 'filename="Invoice_{}_{}_{}.pdf"'.format(
                invoice and invoice.number or pk,
                invoice and invoice.project and invoice.project.title or pk,
                invoice and invoice.title or pk
            )
            return http_response


class PaymentViewSet(ModelViewSet):
    serializer_class = PaymentSerializer
    queryset = Payment.objects.all()
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = PaymentFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (PaymentFilterBackend,)
