# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.tokens import default_token_generator
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.encoding import force_bytes, python_2_unicode_compatible
from django.utils.http import urlsafe_base64_encode
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga_projects.models import DeveloperRating
from tunga_utils import bitcoin_utils, coinbase_utils
from tunga_utils.constants import PAYMENT_METHOD_BTC_ADDRESS, \
    PAYMENT_METHOD_BTC_WALLET, BTC_WALLET_PROVIDER_COINBASE, \
    USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER, USER_TYPE_PROJECT_MANAGER, \
    USER_SOURCE_DEFAULT, \
    USER_SOURCE_TASK_WIZARD, STATUS_INITIAL, STATUS_APPROVED, STATUS_DECLINED, \
    STATUS_PENDING, USER_SOURCE_MANUAL, \
    STATUS_INITIATED, USER_CATEGORY_DEVELOPER, USER_CATEGORY_DESIGNER
from tunga_utils.validators import validate_file_size

USER_TYPE_CHOICES = (
    (USER_TYPE_DEVELOPER, 'Developer'),
    (USER_TYPE_PROJECT_OWNER, 'Project Owner'),
    (USER_TYPE_PROJECT_MANAGER, 'Project Manager')
)

USER_CATEGORY_CHOICES = (
    (USER_CATEGORY_DEVELOPER, 'Developer'),
    (USER_CATEGORY_DESIGNER, 'Designer')
)

USER_SOURCE_CHOICES = (
    (USER_SOURCE_DEFAULT, 'Default'),
    (USER_SOURCE_TASK_WIZARD, 'Task Wizard'),
    (USER_SOURCE_MANUAL, 'Manual'),
)

PAYONEER_STATUS_CHOICES = (
    (STATUS_INITIAL, 'Initial'),
    (STATUS_INITIATED, 'Initiated'),
    (STATUS_PENDING, 'Pending'),
    (STATUS_APPROVED, 'Approved'),
    (STATUS_DECLINED, 'Decline')
)


class TungaUser(AbstractUser):
    type = models.IntegerField(choices=USER_TYPE_CHOICES, blank=True, null=True)
    category = models.CharField(max_length=20, choices=USER_CATEGORY_CHOICES,
                                blank=True, null=True)
    is_internal = models.BooleanField(default=False)
    image = models.ImageField(upload_to='photos/%Y/%m/%d', blank=True,
                              null=True, validators=[validate_file_size])
    verified = models.BooleanField(default=False)
    pending = models.BooleanField(default=True)
    source = models.IntegerField(choices=USER_SOURCE_CHOICES,
                                 default=USER_SOURCE_DEFAULT)
    last_activity_at = models.DateTimeField(blank=True, null=True)
    last_set_password_email_at = models.DateTimeField(blank=True, null=True)
    agree_version = models.FloatField(blank=True, null=True, default=0)
    agreed_at = models.DateTimeField(blank=True, null=True)
    disagree_version = models.FloatField(blank=True, null=True, default=0)
    disagreed_at = models.DateTimeField(blank=True, null=True)
    payoneer_signup_url = models.URLField(blank=True, null=False)
    payoneer_status = models.CharField(
        max_length=20, choices=PAYONEER_STATUS_CHOICES,
        help_text=', '.join(['{} - {}'.format(item[0], item[1]) for item in
                             PAYONEER_STATUS_CHOICES]),
        default=STATUS_INITIAL
    )
    invoice_email = models.EmailField(blank=True, null=True)
    can_pay = models.BooleanField(default=False)
    sso_uuid = models.UUIDField(null=True, blank=True)
    sso_refresh_token = models.TextField(null=True, blank=True)

    class Meta(AbstractUser.Meta):
        unique_together = ('email',)

    def save(self, *args, **kwargs):
        if self.type == USER_TYPE_PROJECT_OWNER:
            self.pending = False
        elif self.type == USER_TYPE_DEVELOPER and not self.category:
            self.category = USER_CATEGORY_DEVELOPER
        super(TungaUser, self).save(*args, **kwargs)

    def __str__(self):
        return '{} ({})'.format(self.display_name, self.get_username())

    def get_absolute_url(self):
        return '/developer/{}/'.format(self.username)

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_authenticated()

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user.is_authenticated() and request.user.id == self.id

    @property
    def display_name(self):
        return (self.get_full_name() or self.username).title()

    @property
    def short_name(self):
        return (self.get_short_name() or self.username).title()

    @property
    def name(self):
        return (self.get_full_name() or self.username).title()

    @property
    def display_type(self):
        if self.category == USER_CATEGORY_DESIGNER:
            return self.get_category_display()
        return self.get_type_display()

    @property
    def display_category(self):
        if self.type == USER_TYPE_DEVELOPER and not self.category:
            return 'Developer'
        elif self.category == USER_CATEGORY_DESIGNER:
            return 'Designer'
        return self.get_category_display()

    @property
    def is_admin(self):
        return self.is_staff or self.is_superuser

    @property
    def is_pay_admin(self):
        return self.is_admin and self.can_pay

    @property
    def is_developer(self):
        return self.type == USER_TYPE_DEVELOPER

    @property
    def is_designer(self):
        return self.type == USER_TYPE_DEVELOPER and self.category == USER_CATEGORY_DESIGNER

    @property
    def is_project_owner(self):
        return self.type == USER_TYPE_PROJECT_OWNER

    @property
    def is_project_manager(self):
        return self.type == USER_TYPE_PROJECT_MANAGER

    @property
    def avatar_url(self):
        if self.image:
            return self.image.url
        social_accounts = self.socialaccount_set.all()
        if social_accounts:
            return social_accounts[0].get_avatar_url()
        return None

    @property
    def profile(self):
        try:
            return self.userprofile
        except:
            return None

    @property
    def company(self):
        try:
            return self.user_company
        except:
            return None

    @property
    def payment_method(self):
        if not self.profile:
            return None
        return self.profile.payment_method

    @property
    def mobile_money_cc(self):
        if not self.profile:
            return None
        return self.profile.mobile_money_cc

    @property
    def phone_number(self):
        if not self.profile:
            return None
        return self.profile.phone_number

    @property
    def mobile_money_number(self):
        if not self.profile:
            return None
        return self.profile.mobile_money_number

    @property
    def btc_address(self):
        if not self.profile:
            return None

        if self.profile.payment_method == PAYMENT_METHOD_BTC_ADDRESS:
            if bitcoin_utils.is_valid_btc_address(self.profile.btc_address):
                return self.profile.btc_address
        elif self.profile.payment_method == PAYMENT_METHOD_BTC_WALLET:
            wallet = self.profile.btc_wallet
            if wallet.provider == BTC_WALLET_PROVIDER_COINBASE:
                client = coinbase_utils.get_oauth_client(wallet.token,
                                                         wallet.token_secret,
                                                         self)
                return coinbase_utils.get_new_address(client)
        return None

    @property
    def is_confirmed(self):
        return self.emailaddress_set.filter(verified=True).count() > 0

    @property
    def uid(self):
        return urlsafe_base64_encode(force_bytes(self.pk))

    def generate_reset_token(self):
        return default_token_generator.make_token(self)

    @property
    def exact_code(self):
        return '{0:018d}'.format(self.id)

    @property
    def tax_rate(self):
        if self.profile and self.profile.country and self.profile.country.code == 'NL':
            return 21
        return 0

    @property
    def tax_location(self):
        client_country = ''
        if self.is_project_owner and self.company and self.company.country and self.company.country.code:
            client_country = self.company.country.code
        elif self.profile and self.profile.country and self.profile.country.code:
            client_country = self.profile.country.code
        if client_country == 'NL':
            return 'NL'
        elif client_country in [
            # EU members
            'BE', 'BG', 'CZ', 'DK', 'DE', 'EE', 'IE', 'EL', 'ES', 'FR', 'HR',
            'IT', 'CY', 'LV', 'LT', 'LU',
            'HU', 'MT', 'AT', 'PL', 'PT', 'RO', 'SI', 'SK', 'FI', 'SE', 'UK'
            # European Free Trade Association (EFTA)
                                                                        'IS',
            'LI', 'NO', 'CH'
        ]:
            return 'europe'
        else:
            return 'world'

    @property
    def profile_rank(self):
        total_score = 0
        total_score += sum(
            [item.status == STATUS_APPROVED and 0.3 or 0.15 for item in
             self.project_participation.filter(
                 status__in=[STATUS_INITIAL, STATUS_APPROVED])])
        total_score += sum([getattr(self, k, None) and 0.1 or 0 for k in
                            ['first_name', 'last_name', 'email']])
        if self.profile:
            total_score += sum(
                [(getattr(self.profile, k, None)) and 0.1 or 0 for k in
                 ['country', 'city', 'street', 'plot_number', 'postal_code',
                  'id_document']])
        work_count = self.work_set.all().count()
        if work_count > 3:
            total_score += (3 * 0.2) + ((work_count - 3) * 0.02)
        else:
            total_score += (work_count * 0.02)
        total_score += self.education_set.all().count() * 0.04
        return total_score

    @property
    def average_rating(self):
        month_ago = datetime.datetime.utcnow() - relativedelta(days=30)
        now = datetime.datetime.utcnow()
        rating_count = DeveloperRating.objects.filter(
            created_at__range=[month_ago, now],
            user=self
        ).count()
        rating = DeveloperRating.objects.filter(
            created_at__range=[month_ago, now],
            user=self
        ).aggregate(rating=Coalesce(Sum('rating'), 0))
        if rating_count == 0:
            return "%.2f" % 0.00
        else:
            rating_ = float(rating['rating']) / float(rating_count)
            return "%.2f" % rating_


@python_2_unicode_compatible
class EmailVisitor(models.Model):
    email = models.EmailField(unique=True)
    via_search = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email

    class Meta:
        ordering = ['-created_at']
