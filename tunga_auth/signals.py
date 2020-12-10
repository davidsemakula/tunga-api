import random
import string

from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_auth.models import EmailVisitor
from tunga_auth.notifications import send_new_user_password_email
from tunga_auth.tasks import sync_hubspot_contact, sync_hubspot_email
from tunga_profiles import sso_helper
from tunga_profiles.tasks import sync_algolia_user
from tunga_projects.notifications.slack import notify_new_user_signup_on_platform
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER, USER_SOURCE_MANUAL


@receiver(post_save, sender=get_user_model())
def activity_handler_new_user(sender, instance, created, **kwargs):
    if created and instance.source == USER_SOURCE_MANUAL:
        if not EmailAddress.objects.filter(email=instance.email).count():
            email_address = EmailAddress.objects.add_email(
                None, instance, instance.email
            )

            email_address.verified = True
            email_address.primary = True
            email_address.save()

        send_new_user_password_email.delay(instance.id)
        random_string = ''.join(random.choice(string.ascii_lowercase) for _ in range(18))
        instance.sso_refresh_token = random_string
        instance.save()
        sso_helper.sync_user_sso(user=instance, password=random_string, over_ride=False)

        if instance.is_developer:
            sync_algolia_user.delay(instance.id)


@receiver(user_signed_up)
def activity_handler_new_signup(request, user, **kwargs):
    notify_new_user_signup_on_platform.delay(user.id)

    if user.type == USER_TYPE_PROJECT_OWNER:
        sync_hubspot_contact.delay(user.id)


@receiver(post_save, sender=EmailVisitor)
def activity_handler_new_email_visitor(sender, instance, created, **kwargs):
    if created:
        sync_hubspot_email.delay(instance.email)
