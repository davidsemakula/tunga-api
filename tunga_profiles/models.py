# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import uuid

import tagulous.models
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django_countries.fields import CountryField
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga_profiles.validators import validate_email
from tunga_utils.constants import REQUEST_STATUS_INITIAL, \
    REQUEST_STATUS_ACCEPTED, REQUEST_STATUS_REJECTED, \
    BTC_WALLET_PROVIDER_COINBASE, PAYMENT_METHOD_BTC_WALLET, \
    PAYMENT_METHOD_BTC_ADDRESS, PAYMENT_METHOD_MOBILE_MONEY, \
    COUNTRY_CODE_UGANDA, COUNTRY_CODE_TANZANIA, COUNTRY_CODE_NIGERIA, \
    APP_INTEGRATION_PROVIDER_SLACK, \
    APP_INTEGRATION_PROVIDER_HARVEST, USER_TYPE_PROJECT_MANAGER, \
    USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER, \
    STATUS_INITIAL, STATUS_ACCEPTED, STATUS_REJECTED, SKILL_TYPE_LANGUAGE, \
    SKILL_TYPE_FRAMEWORK, \
    SKILL_TYPE_PLATFORM, SKILL_TYPE_LIBRARY, SKILL_TYPE_STORAGE, SKILL_TYPE_API, \
    SKILL_TYPE_OTHER, USER_CATEGORY_DEVELOPER, USER_CATEGORY_DESIGNER, \
    PROFILE_PROJECT_CATEGORY_CHOICES
from tunga_utils.helpers import get_serialized_id
from tunga_utils.models import AbstractExperience
from tunga_utils.validators import validate_btc_address

SKILL_TYPE_CHOICES = (
    (SKILL_TYPE_LANGUAGE, 'Language'),
    (SKILL_TYPE_FRAMEWORK, 'Framework'),
    (SKILL_TYPE_PLATFORM, 'Platform'),
    (SKILL_TYPE_LIBRARY, 'Library'),
    (SKILL_TYPE_STORAGE, 'Storage Engine'),
    (SKILL_TYPE_API, 'API'),
    (SKILL_TYPE_OTHER, 'Other')
)


class Skill(tagulous.models.TagModel):
    type = models.CharField(
        max_length=30, choices=SKILL_TYPE_CHOICES, default=SKILL_TYPE_OTHER,
        help_text=','.join(
            ['%s - %s' % (item[0], item[1]) for item in SKILL_TYPE_CHOICES])
    )
    primary = models.BooleanField(default=False)

    class TagMeta:
        initial = "PHP, JavaScript, Python, Ruby, Java, C#, C++, Ruby, Swift, Objective C, .NET, ASP.NET, Node.js," \
                  "HTML, CSS, HTML5, CSS3, XML, JSON, YAML," \
                  "Django, Ruby on Rails, Flask, Yii, Lavarel, Express.js, Spring, JAX-RS," \
                  "AngularJS, React.js, Meteor.js, Ember.js, Backbone.js," \
                  "WordPress, Joomla, Drupal," \
                  "jQuery, jQuery UI, Bootstrap, AJAX," \
                  "Android, iOS, Windows Mobile, Apache Cordova, Ionic," \
                  "SQL, MySQL, PostgreSQL, MongoDB, CouchDB," \
                  "Git, Subversion, Mercurial, " \
                  "Docker, Ansible, " \
                  "Webpack, Grunt, Gulp, Ant, Maven, Gradle"
        space_delimiter = False


class City(tagulous.models.TagModel):
    class TagMeta:
        initial = "Kampala, Entebbe, Jinja, Nairobi, Mombosa, Dar es Salaam, Kigali, Amsterdam"


BTC_WALLET_PROVIDER_CHOICES = (
    (BTC_WALLET_PROVIDER_COINBASE, 'Coinbase'),
)


@python_2_unicode_compatible
class BTCWallet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(
        max_length=30, choices=BTC_WALLET_PROVIDER_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in
                            BTC_WALLET_PROVIDER_CHOICES])
    )
    token = models.TextField(verbose_name='token',
                             help_text='"oauth_token" (OAuth1) or access token (OAuth2)')
    token_secret = models.TextField(
        blank=True, verbose_name='token secret',
        help_text='"oauth_token_secret" (OAuth1) or refresh token (OAuth2)'
    )
    expires_at = models.DateTimeField(blank=True, null=True,
                                      verbose_name='expires at')
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'provider')
        verbose_name = 'bitcoin wallet'

    def __str__(self):
        return '%s - %s' % (
            self.user.get_short_name(), self.get_provider_display())


APP_INTEGRATION_PROVIDER_CHOICES = (
    (APP_INTEGRATION_PROVIDER_SLACK, 'Slack'),
    (APP_INTEGRATION_PROVIDER_HARVEST, 'Harvest'),
)


@python_2_unicode_compatible
class AppIntegration(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(
        max_length=30, choices=APP_INTEGRATION_PROVIDER_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in
                            APP_INTEGRATION_PROVIDER_CHOICES])
    )
    token = models.TextField(verbose_name='token',
                             help_text='"oauth_token" (OAuth1) or access token (OAuth2)')
    token_secret = models.TextField(
        blank=True, verbose_name='token secret',
        help_text='"oauth_token_secret" (OAuth1) or refresh token (OAuth2)'
    )
    extra = models.TextField(blank=True,
                             null=True)  # JSON formatted extra details
    expires_at = models.DateTimeField(blank=True, null=True,
                                      verbose_name='expires at')
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'provider')
        verbose_name = 'app integration'
        verbose_name_plural = 'app integrations'

    def __str__(self):
        return '%s - %s' % (
            self.user.get_short_name(), self.get_provider_display())


PAYMENT_METHOD_CHOICES = (
    (PAYMENT_METHOD_BTC_WALLET, 'Bitcoin Wallet'),
    (PAYMENT_METHOD_BTC_ADDRESS, 'Bitcoin Address'),
    (PAYMENT_METHOD_MOBILE_MONEY, 'Mobile Money')
)

MOBILE_MONEY_CC_CHOICES = (
    (COUNTRY_CODE_NIGERIA, 'Nigeria (+234)'),
    (COUNTRY_CODE_TANZANIA, 'Tanzania (+255)'),
    (COUNTRY_CODE_UGANDA, 'Uganda (+256)'),
)


@python_2_unicode_compatible
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE)

    # Personal Info
    bio = models.TextField(blank=True, null=True)

    # Contact Info
    country = CountryField(blank=True, null=True)
    city = tagulous.models.SingleTagField(to=City, blank=True, null=True)
    street = models.CharField(max_length=100, blank=True, null=True)
    plot_number = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    postal_address = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    # Professional Info
    skills = tagulous.models.TagField(to=Skill, blank=True)

    # KYC
    id_document = models.ImageField(upload_to='ids/%Y/%m/%d', blank=True,
                                    null=True)
    company = models.CharField(max_length=200, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    company_profile = models.TextField(blank=True, null=True)
    company_bio = models.TextField(blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    company_reg_no = models.CharField(max_length=50, blank=True, null=True)
    reference_number = models.CharField(max_length=50, blank=True, null=True)
    company_details = models.CharField(max_length=50, blank=True, null=True)

    # Payment Information
    payment_method = models.CharField(
        max_length=30, choices=PAYMENT_METHOD_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in
                            PAYMENT_METHOD_CHOICES]),
        blank=True, null=True
    )
    btc_wallet = models.ForeignKey(BTCWallet, blank=True, null=True,
                                   on_delete=models.SET_NULL)
    btc_address = models.CharField(max_length=40, blank=True, null=True,
                                   validators=[validate_btc_address])
    mobile_money_cc = models.CharField(
        max_length=5, choices=MOBILE_MONEY_CC_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in
                            MOBILE_MONEY_CC_CHOICES]),
        blank=True, null=True)
    mobile_money_number = models.CharField(max_length=15, blank=True, null=True)

    # Tax Information
    tax_name = models.CharField(max_length=200, blank=True, null=True)
    tax_percentage = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.user.get_short_name()

    @property
    def city_name(self):
        return self.city and str(self.city) or ""

    @property
    def country_name(self):
        return unicode(self.country.name)

    @property
    def location(self):
        location = self.city
        if self.country_name:
            location = '{}{}{}'.format(location, location and ', ' or '',
                                       unicode(self.country.name))
        return location or ''

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    def get_category_skills(self, skill_type):
        return self.skills.filter(type=skill_type)

    @property
    def skills_details(self):
        return dict(
            language=self.get_category_skills(SKILL_TYPE_LANGUAGE),
            framework=self.get_category_skills(SKILL_TYPE_FRAMEWORK),
            platform=self.get_category_skills(SKILL_TYPE_PLATFORM),
            library=self.get_category_skills(SKILL_TYPE_LIBRARY),
            storage=self.get_category_skills(SKILL_TYPE_STORAGE),
            api=self.get_category_skills(SKILL_TYPE_API),
            other=self.get_category_skills(SKILL_TYPE_OTHER),
        )


@python_2_unicode_compatible
class Company(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name='user_company')

    # Description
    name = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    # Contact Info
    country = CountryField(blank=True, null=True)
    city = tagulous.models.SingleTagField(to=City, blank=True, null=True)
    street = models.CharField(max_length=100, blank=True, null=True)
    plot_number = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    postal_address = models.CharField(max_length=100, blank=True, null=True)
    tel_number = models.CharField(max_length=15, blank=True, null=True)

    # Stack
    skills = tagulous.models.TagField(to=Skill, blank=True)

    # KYC
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    reg_no = models.CharField(max_length=50, blank=True, null=True)
    ref_no = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = 'company'
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name or 'Company #{}'.format(self.id)

    @property
    def city_name(self):
        return self.city and str(self.city) or ""

    @property
    def country_name(self):
        return str(self.country.name)

    @property
    def location(self):
        location = self.city
        if self.country_name:
            location = '{}{}{}'.format(location, location and ', ' or '',
                                       self.country.name)
        return location or ''

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    def get_category_skills(self, skill_type):
        return self.skills.filter(type=skill_type)

    @property
    def skills_details(self):
        return dict(
            language=self.get_category_skills(SKILL_TYPE_LANGUAGE),
            framework=self.get_category_skills(SKILL_TYPE_FRAMEWORK),
            platform=self.get_category_skills(SKILL_TYPE_PLATFORM),
            library=self.get_category_skills(SKILL_TYPE_LIBRARY),
            storage=self.get_category_skills(SKILL_TYPE_STORAGE),
            api=self.get_category_skills(SKILL_TYPE_API),
            other=self.get_category_skills(SKILL_TYPE_OTHER),
        )


@python_2_unicode_compatible
class Education(AbstractExperience):
    institution = models.CharField(max_length=200)
    award = models.CharField(max_length=200)

    def __str__(self):
        return '%s - %s' % (self.user.get_short_name, self.institution)

    class Meta:
        verbose_name_plural = 'education'


@python_2_unicode_compatible
class Work(AbstractExperience):
    company = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    project_link = models.CharField(max_length=255, null=True, blank=True)
    repository_link = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return '%s - %s' % (self.user.get_short_name, self.company)

    class Meta:
        verbose_name_plural = 'work'


@python_2_unicode_compatible
class ProfileProject(AbstractExperience):
    title = models.CharField(max_length=500)
    category = models.CharField(
        max_length=50, choices=PROFILE_PROJECT_CATEGORY_CHOICES)
    project_link = models.CharField(max_length=255, null=True, blank=True)
    repository_link = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return '%s - %s' % (self.user.get_short_name, self.title)

    class Meta:
        verbose_name_plural = 'project'


CONNECTION_STATUS_CHOICES = (
    (STATUS_INITIAL, 'Initial'),
    (STATUS_ACCEPTED, 'Accepted'),
    (STATUS_REJECTED, 'Rejected')
)


@python_2_unicode_compatible
class Connection(models.Model):
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='connections_initiated')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name='connection_requests')
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    status = models.CharField(
        max_length=30, choices=CONNECTION_STATUS_CHOICES,
        default=STATUS_INITIAL,
        help_text=', '.join(['%s - %s' % (item[0], item[1]) for item in
                             CONNECTION_STATUS_CHOICES])
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s -> %s' % (
            self.from_user.get_short_name, self.to_user.get_short_name)

    class Meta:
        ordering = ['-created_at']

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.from_user or request.user == self.to_user

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.from_user or request.user == self.to_user


APPLICATION_STATUS_CHOICES = (
    (REQUEST_STATUS_INITIAL, 'Received'),
    (REQUEST_STATUS_ACCEPTED, 'Accepted'),
    (REQUEST_STATUS_REJECTED, 'Rejected')
)


@python_2_unicode_compatible
class DeveloperApplication(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(unique=True, validators=[validate_email])
    phone_number = models.CharField(max_length=15)
    country = CountryField()
    city = models.CharField(max_length=50)
    stack = models.TextField()
    experience = models.TextField()
    discovery_story = models.TextField()
    status = models.PositiveSmallIntegerField(
        choices=APPLICATION_STATUS_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in
                            APPLICATION_STATUS_CHOICES]),
        default=REQUEST_STATUS_INITIAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmation_key = models.UUIDField(default=uuid.uuid4, editable=False,
                                        unique=True)
    confirmation_sent_at = models.DateTimeField(blank=True, null=True,
                                                editable=False)
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(blank=True, null=True, editable=False)

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return '%s %s' % (self.first_name, self.last_name)

    @property
    def country_name(self):
        return self.country.name

    country_name.fget.short_description = 'country'


USER_TYPE_CHOICES = (
    (USER_TYPE_DEVELOPER, 'Developer'),
    (USER_TYPE_PROJECT_OWNER, 'Project Owner'),
    (USER_TYPE_PROJECT_MANAGER, 'Project Manager')
)

USER_CATEGORY_CHOICES = (
    (USER_CATEGORY_DEVELOPER, 'Developer'),
    (USER_CATEGORY_DESIGNER, 'Designer')
)


@python_2_unicode_compatible
class DeveloperInvitation(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(unique=True, validators=[validate_email])
    type = models.IntegerField(choices=USER_TYPE_CHOICES,
                               default=USER_TYPE_DEVELOPER)
    category = models.CharField(max_length=20, choices=USER_CATEGORY_CHOICES,
                                blank=True, null=True)

    invitation_key = models.UUIDField(default=uuid.uuid4, editable=False,
                                      unique=True)
    invitation_sent_at = models.DateTimeField(blank=True, null=True,
                                              editable=False)
    used = models.BooleanField(default=False)  # pending invitation
    used_at = models.DateTimeField(blank=True, null=True, editable=False)
    resent = models.BooleanField(default=False)
    resent_at = models.DateTimeField(blank=True, null=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'user invitation'

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return '%s %s' % (self.first_name, self.last_name)

    @property
    def display_type(self):
        if self.type == USER_TYPE_DEVELOPER:
            if self.category and self.category == USER_CATEGORY_DESIGNER:
                return USER_CATEGORY_DESIGNER.title()
            else:
                return self.get_type_display()
        else:
            return self.get_type_display()


@python_2_unicode_compatible
class UserNumber(models.Model):
    """
    Helper table for generating user numbers in a sequence
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.number

    class Meta:
        abstract = True

    @property
    def number(self):
        return get_serialized_id(self.id, max_digits=4)


class ClientNumber(UserNumber):
    """
    Helper table for generating client numbers in a sequence
    """
    pass


class DeveloperNumber(UserNumber):
    """
    Helper table for generating developer numbers in a sequence
    """
    pass


@python_2_unicode_compatible
class Inquirer(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s (%s)' % (self.name, self.email or self.id)

    class Meta:
        ordering = ['-created_at']


@python_2_unicode_compatible
class UserRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.DO_NOTHING,
                             related_name='user_requests')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.DO_NOTHING,
                                   related_name='users_requested')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '{} requested {}'.format(self.created_by.short_name(),
                                        self.user.short_name())


@python_2_unicode_compatible
class WhitePaperUser(models.Model):
    white_paper_choices = (
        ('best_african_countries_for_outsourcing',
         'best_african_countries_for_outsourcing'),
        ('scaling_your_team_with_remote_developers',
         'scaling_your_team_with_remote_developers')
    )
    paper = models.CharField(max_length=255, choices=white_paper_choices)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    company = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    phone_number = models.CharField(max_length=20)
    country = CountryField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '{} {} - {}'.format(self.first_name, self.email, self.company)
