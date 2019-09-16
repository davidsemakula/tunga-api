import uuid

from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault
from rest_framework.serializers import ListSerializer

from tunga_payments.models import Payment, Invoice
from tunga_projects.serializers import NestedProjectSerializer, SimpleProgressEventSerializer
from tunga_utils.constants import PAYMENT_METHOD_STRIPE
from tunga_utils.serializers import NestedModelSerializer, ContentTypeAnnotatedModelSerializer, \
    CreateOnlyCurrentUserDefault, SimplestUserSerializer, SimpleModelSerializer


class SimpleInvoiceSerializer(SimpleModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    updated_by = SimplestUserSerializer(required=False, read_only=True, default=CurrentUserDefault())
    user = SimplestUserSerializer()
    full_title = serializers.CharField(read_only=True)
    tax_amount = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
    download_url = serializers.CharField(read_only=True)
    due_at = serializers.DateTimeField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        exclude = ('project',)


class InvoiceListSerializer(ListSerializer):

    def create(self, validated_data):
        group_batch_ref = uuid.uuid4()
        invoices = [Invoice(batch_ref=group_batch_ref, **item) for item in validated_data]
        return Invoice.objects.bulk_create(invoices)


class InvoiceSerializer(NestedModelSerializer, ContentTypeAnnotatedModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    updated_by = SimplestUserSerializer(required=False, read_only=True, default=CurrentUserDefault())
    project = NestedProjectSerializer()
    user = SimplestUserSerializer()
    full_title = serializers.CharField(read_only=True)
    milestone = SimpleProgressEventSerializer(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
    download_url = serializers.CharField(read_only=True)
    due_at = serializers.DateTimeField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'


class BulkInvoiceSerializer(serializers.Serializer):
    title = serializers.CharField(required=True)
    project = NestedProjectSerializer()
    milestone = SimpleProgressEventSerializer(required=False, allow_null=True)
    invoices = serializers.ListField(child=InvoiceSerializer())

    class Meta:
        model = Invoice


class PaymentSerializer(NestedModelSerializer, ContentTypeAnnotatedModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    invoice = SimpleInvoiceSerializer()

    class Meta:
        model = Payment
        fields = '__all__'


class StripePaymentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(required=True, choices=(
        (PAYMENT_METHOD_STRIPE, 'Stripe')
    ))
    amount = serializers.DecimalField(required=True, max_digits=17, decimal_places=2)
    token = serializers.CharField(required=True)


class StripePaymentIntentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(required=True, choices=(
        (PAYMENT_METHOD_STRIPE, 'Stripe')
    ))
    amount = serializers.DecimalField(required=True, max_digits=17, decimal_places=2)


class StripePaymentIntentCompleteSerializer(serializers.Serializer):
    id = serializers.CharField(required=True, max_length=100)
    amount = serializers.DecimalField(required=True, max_digits=17, decimal_places=2)
