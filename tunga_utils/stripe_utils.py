import stripe
from decimal import Decimal

from tunga.settings import STRIPE_SECRET


def get_client():
    stripe.api_key = STRIPE_SECRET
    # client = stripe.http_client.RequestsClient()
    # stripe.default_http_client = client
    return stripe


def calculate_total_payment(amount, cents=False):
    return ((Decimal(amount)*Decimal('1.029')) + Decimal(0.25))*(cents and Decimal(100) or 1)


def calculate_payment_fee(amount, cents=False):
    return ((Decimal(amount)*Decimal('0.029')) + Decimal(0.25))*(cents and Decimal(100) or 1)
