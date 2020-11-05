from datetime import datetime

import django_filters
from dateutil.relativedelta import relativedelta
from django_filters import FilterSet

from tunga_payments.models import Invoice, Payment
from tunga_utils.constants import INVOICE_TYPE_SALE, INVOICE_TYPE_PURCHASE, \
    INVOICE_TYPE_SALE_DUE_DATE, INVOICE_TYPE_PURCHASE_DUE_DATE
from tunga_utils.filters import GenericDateFilterSet


class InvoiceFilter(GenericDateFilterSet):
    class Meta:
        model = Invoice
        fields = ('type', 'batch_ref', 'number', 'user', 'project', 'created_by', 'paid', 'status', 'overdue',)

    def filter_overdue(self, queryset, name, value):
        type = self.data.get('type', None)
        if type:
            days_when_invoice_is_due = 0
            if type == INVOICE_TYPE_SALE:
                days_when_invoice_is_due = INVOICE_TYPE_SALE_DUE_DATE
            elif type == INVOICE_TYPE_PURCHASE:
                days_when_invoice_is_due = INVOICE_TYPE_PURCHASE_DUE_DATE
            due_date = (
                datetime.utcnow() - relativedelta(days=days_when_invoice_is_due)).replace(hour=23,
                                                                      minute=59,
                                                                      second=59,
                                                                      microsecond=999999)

            return queryset.filter(
                issued_at__lte=due_date, paid=False
            )
        return queryset


class PaymentFilter(FilterSet):
    batch_ref = django_filters.CharFilter(name='invoice__batch_ref', label='Invoice Batch Ref', lookup_expr='exact')
    number = django_filters.NumberFilter(name='invoice__number', label='Invoice number', lookup_expr='exact')
    project = django_filters.NumberFilter(name='invoice__project', label='Project Invoice', lookup_expr='exact')
    user = django_filters.NumberFilter(name='invoice__user', label='Invoice user', lookup_expr='exact')
    min_date = django_filters.IsoDateTimeFilter(name='paid_at', lookup_expr='gte')
    max_date = django_filters.IsoDateTimeFilter(name='paid_at', lookup_expr='lte')

    class Meta:
        model = Payment
        fields = ('min_date', 'max_date', 'batch_ref', 'number', 'user', 'project', 'created_by',)
