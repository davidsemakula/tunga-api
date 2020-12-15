from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver, Signal

from tunga_activity import verbs
from tunga_profiles.models import Connection, DeveloperApplication, Skill, DeveloperInvitation, UserProfile, UserRequest
from tunga_profiles.notifications import send_new_developer_email, send_developer_accepted_email, \
    send_developer_application_received_email, send_new_skill_email, send_developer_invited_email, \
    notify_user_profile_updated_slack, notify_user_request_slack
from tunga_profiles.tasks import sync_algolia_user
from tunga_utils.constants import REQUEST_STATUS_ACCEPTED, STATUS_ACCEPTED, STATUS_REJECTED
from tunga_utils.signals import post_nested_save

user_profile_updated = Signal(providing_args=["profile"])


@receiver(post_nested_save, sender=UserProfile)
def activity_handler_new_profile(sender, instance, created, **kwargs):
    if instance.user and instance.user.is_developer:
        sync_algolia_user.delay(instance.user.id)


@receiver(post_save, sender=Connection)
def activity_handler_new_connection(sender, instance, created, **kwargs):
    if created:
        action.send(
            instance.from_user, verb=verbs.CONNECT, action_object=instance, target=instance.to_user)
    else:
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            if 'status' in update_fields and instance.status == STATUS_ACCEPTED:
                action.send(instance.to_user, verb=verbs.ACCEPT, action_object=instance)
            elif 'status' in update_fields and not instance.status == STATUS_REJECTED:
                action.send(instance.to_user, verb=verbs.REJECT, action_object=instance)


@receiver(post_save, sender=DeveloperApplication)
def activity_handler_developer_application(sender, instance, created, **kwargs):
    if created:
        send_new_developer_email.delay(instance.id)

        send_developer_application_received_email.delay(instance.id)
    else:
        if instance.status == REQUEST_STATUS_ACCEPTED and not instance.confirmation_sent_at:
            send_developer_accepted_email.delay(instance.id)


@receiver(post_save, sender=Skill)
def activity_handler_new_skill(sender, instance, created, **kwargs):
    if created:
        send_new_skill_email.delay(instance.id)


@receiver(user_profile_updated, sender=UserProfile)
def activity_handler_profile_update(sender, profile, **kwargs):
    notify_user_profile_updated_slack.delay(profile.id)


@receiver(post_save, sender=UserRequest)
def activity_handler_user_request(sender, instance, created, **kwargs):
    if created:
        notify_user_request_slack.delay(instance.id)
