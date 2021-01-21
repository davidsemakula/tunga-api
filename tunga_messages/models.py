from __future__ import unicode_literals

import json
import re

from actstream.models import Action
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.query_utils import Q
from django.utils.encoding import python_2_unicode_compatible
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga_profiles.models import Connection, Inquirer
from tunga_utils.constants import CHANNEL_TYPE_DIRECT, CHANNEL_TYPE_TOPIC, CHANNEL_TYPE_SUPPORT, \
    APP_INTEGRATION_PROVIDER_SLACK, CHANNEL_TYPE_DEVELOPER
from tunga_utils.helpers import GenericObject, convert_to_text, convert_to_html, convert_slack_to_html
from tunga_utils.models import Upload

CHANNEL_TYPE_CHOICES = (
    (CHANNEL_TYPE_DIRECT, 'Direct Channel'),
    (CHANNEL_TYPE_TOPIC, 'Topic Channel'),
    (CHANNEL_TYPE_SUPPORT, 'Support Channel'),
    (CHANNEL_TYPE_DEVELOPER, 'Developer Channel')
)


@python_2_unicode_compatible
class Channel(models.Model):
    subject = models.CharField(max_length=100, blank=True, null=True)
    participants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='ChannelUser', through_fields=('channel', 'user'),
            related_name='channels', blank=True)
    type = models.PositiveSmallIntegerField(
        choices=CHANNEL_TYPE_CHOICES, default=CHANNEL_TYPE_TOPIC,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in CHANNEL_TYPE_CHOICES])
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='channels_created', on_delete=models.DO_NOTHING,
        blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_read = models.IntegerField(default=0)

    # The object of the channel, nullable for pure messages
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, verbose_name=_('content type'), blank=True, null=True
    )
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    attachments = GenericRelation(Upload, related_query_name='channels')
    action_targets = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='channels'
    )

    def __str__(self):
        return '{0} - {1}'.format(self.get_type_display(), self.subject or self.created_by or self.id)

    class Meta:
        ordering = ['-created_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @staticmethod
    @allow_staff_or_superuser
    def has_list_permission(request):
        return request.user.is_authenticated()

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_authenticated()

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        if self.type == CHANNEL_TYPE_SUPPORT:
            return True
        elif not request.user.is_authenticated():
            return False
        if self.type == CHANNEL_TYPE_DEVELOPER and request.user.is_developer:
            return True
        return self.has_object_write_permission(request)

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.created_by or self.channeluser_set.filter(user=request.user).count()

    @allow_staff_or_superuser
    def has_object_update_permission(self, request):
        if self.has_object_write_permission(request):
            return True
        # Developers can upload to developer channels
        is_upload_only = not [x for x in request.data.keys() if not re.match(r'^file\d*$', x)]
        if self.type == CHANNEL_TYPE_DEVELOPER and request.user.is_developer and is_upload_only:
            return True
        return False

    @property
    def all_attachments(self):
        return Upload.objects.filter(Q(channels=self) | Q(messages__channel=self))

    def get_receiver(self, sender):
        if sender and self.type in [CHANNEL_TYPE_DIRECT, CHANNEL_TYPE_TOPIC]:
            participation = self.channeluser_set.filter(~Q(user_id=sender.id))
            if participation and participation.count() == 1:
                return participation[0].user
        return None

    def get_channel_display_name(self, sender):
        if self.type == CHANNEL_TYPE_DIRECT:
            user = self.get_receiver(sender)
            if user:
                return user.display_name
        elif self.subject:
            return self.subject
        elif self.type == CHANNEL_TYPE_SUPPORT:
            try:
                return 'Help: %s' % self.content_object.name
            except:
                pass
        return str(self)

    def get_inquirer(self):
        if self.type == CHANNEL_TYPE_SUPPORT:
            return self.content_object
        return None

    def get_alt_subject(self):
        if self.type == CHANNEL_TYPE_SUPPORT:
            inquirer = self.get_inquirer()
            if inquirer:
                return '%s (Guest)' % inquirer.name
            elif self.created_by:
                return '%s (%s)' % (self.created_by.name, self.created_by.get_type_display())
        if self.subject:
            return self.subject
        return None


@python_2_unicode_compatible
class ChannelUser(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_read = models.IntegerField(default=0)
    last_email_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '%s - %s' % (self.channel, self.user.get_short_name() or self.user.username)

    class Meta:
        unique_together = ('user', 'channel')


@python_2_unicode_compatible
class Message(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages',
        blank=True, null=True
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    alt_user = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=50, blank=True, null=True)
    extra = models.TextField(blank=True, null=True)

    attachments = GenericRelation(Upload, related_query_name='messages')
    activity_objects = GenericRelation(
        Action,
        object_id_field='action_object_object_id',
        content_type_field='action_object_content_type',
        related_query_name='messages'
    )

    def __str__(self):
        return '%s - %s' % (self.user and self.user.get_short_name() or 'Anonymous', self.body)

    class Meta:
        ordering = ['-created_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @staticmethod
    @allow_staff_or_superuser
    def has_list_permission(request):
        return request.user.is_authenticated()

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_authenticated()

    @staticmethod
    @allow_staff_or_superuser
    def has_create_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        if self.has_object_write_permission(request):
            return True
        elif not request.user.is_authenticated():
            return False
        return self.channel.channeluser_set.filter(user=request.user).count()

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        if self.channel and self.channel.type == CHANNEL_TYPE_SUPPORT:
            return True
        elif not request.user.is_authenticated():
            return False
        return request.user == self.user

    @property
    def excerpt(self):
        return strip_tags(convert_slack_to_html(self.body))

    @property
    def text_body(self):
        return convert_to_text(convert_slack_to_html(self.body))

    @property
    def html_body(self):
        return convert_to_html(self.body)

    def get_alt_user(self):
        if not self.alt_user:
            return None
        try:
            user = GenericObject(**json.loads(self.alt_user))
            if self.source == APP_INTEGRATION_PROVIDER_SLACK:
                user.name = '%s from Tunga' % user.name.title()
                user.avatar_url = 'https://work.tunga.io/icons/Tunga_squarex150.png'
            user.display_name = user.name
            user.short_name = user.name
            return user
        except:
            return None

    @property
    def inquirer(self):
        return self.channel.content_object

    @property
    def sender(self):
        if self.user:
            if (self.user.is_staff or self.user.is_superuser) and \
                            self.channel.type in [CHANNEL_TYPE_SUPPORT, CHANNEL_TYPE_DEVELOPER]:
                support_name = '%s from Tunga' % self.user.short_name
                user = GenericObject(**dict(
                    id=self.user_id,
                    name=support_name,
                    display_name=support_name,
                    short_name=support_name,
                    email=self.user.email,
                    avatar_url=self.user.avatar_url or 'https://work.tunga.io/icons/Tunga_squarex150.png'
                ))
                return user
            return self.user
        alt_user = self.get_alt_user()
        if alt_user:
            return alt_user
        inquirer = self.inquirer
        if inquirer:
            return GenericObject(**dict(
                id='inquirer#{}'.format(inquirer.id),
                name=inquirer.name,
                display_name=(inquirer.name or '').title(),
                short_name=(inquirer.name or '').title(),
                email=inquirer.email,
                inquirer=True
            ))
        return GenericObject(**dict(
            id='visitor#{}'.format(self.channel.id),
            name='Guest',
            display_name='Guest',
            short_name='Guest',
            inquirer=True
        ))
