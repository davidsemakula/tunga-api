from actstream import action
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal

from tunga_activity import verbs
from tunga_projects.models import Project, Participation, Document, \
    ProgressEvent, ProgressReport, InterestPoll, DeveloperRating
from tunga_projects.notifications.generic import notify_new_project, \
    notify_new_participant, notify_new_progress_report, \
    notify_interest_poll_status, notify_new_developer_rating
from tunga_projects.notifications.slack import notify_new_progress_report_slack, \
    notify_new_developer_rating_slack
from tunga_projects.tasks import sync_hubspot_deal, manage_interest_polls, activate_project
from tunga_utils.constants import PROJECT_STAGE_OPPORTUNITY, STATUS_INTERESTED, STATUS_INITIAL, PROJECT_STAGE_ACTIVE
from tunga_utils.signals import post_nested_save, post_field_update


@receiver(post_save, sender=Project)
def activity_handler_new_project(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=verbs.CREATE, action_object=instance)


@receiver(post_nested_save, sender=Project)
def activity_handler_new_full_project(sender, instance, created, **kwargs):
    if not instance.legacy_id:
        if created:
            notify_new_project.delay(instance.id)

            if instance.stage == PROJECT_STAGE_OPPORTUNITY:
                manage_interest_polls(instance.id, remind=False)

        if instance.stage != PROJECT_STAGE_OPPORTUNITY:
            # Don't sync opportunities to HubSpot
            sync_hubspot_deal.delay(instance.id)


@receiver(post_field_update, sender=Project)
def activity_handler_updated_project_field(sender, instance, field, **kwargs):
    if field == 'stage' and instance.stage == PROJECT_STAGE_ACTIVE:
        action.send(instance.user, verb=verbs.ACTIVATE, action_object=instance)
        activate_project(instance.id)


@receiver(post_save, sender=Participation)
def activity_handler_new_participation(sender, instance, created, **kwargs):
    if created and not instance.legacy_id:
        action.send(instance.created_by, verb=verbs.CREATE, action_object=instance, target=instance.project)

        notify_new_participant.delay(instance.id)


@receiver(post_save, sender=Document)
def activity_handler_new_document(sender, instance, created, **kwargs):
    if created and not instance.legacy_id:
        action.send(instance.created_by, verb=verbs.CREATE, action_object=instance, target=instance.project)


@receiver(post_save, sender=ProgressEvent)
def activity_handler_new_progress_event(sender, instance, created, **kwargs):
    if created and not instance.legacy_id:
        action.send(
            instance.created_by or instance.project.owner or instance.project.user,
            verb=verbs.CREATE, action_object=instance, target=instance.project
        )


@receiver(post_save, sender=ProgressReport)
def activity_handler_new_progress_report(sender, instance, created, **kwargs):
    if created and not instance.legacy_id:
        action.send(instance.user, verb=verbs.CREATE, action_object=instance, target=instance.event)
        notify_new_progress_report.delay(instance.id)
    elif not instance.legacy_id:
        notify_new_progress_report_slack.delay(instance.id, updated=True)


@receiver(post_save, sender=DeveloperRating)
def activity_handler_new_developer_rating(sender, instance, created, **kwargs):
    if created:
        # action.send(instance.user, verb=verbs.CREATE, action_object=instance, target=instance.event)
        notify_new_developer_rating.delay(instance.id)
    else:
        notify_new_developer_rating_slack.delay(instance.id, updated=True)


@receiver(post_field_update, sender=InterestPoll)
def activity_handler_updated_interest_poll_field(sender, instance, field, **kwargs):
    if field == 'status' and instance.status != STATUS_INITIAL:
        action.send(
            instance.user,
            verb=instance.status == STATUS_INTERESTED and verbs.ACCEPT or verbs.REJECT,
            action_object=instance, target=instance.project
        )
        notify_interest_poll_status.delay(instance.id)

    if field == 'approval_status' and instance.approval_status != STATUS_INITIAL:
        action.send(
            instance.user,
            verb=instance.status == STATUS_INTERESTED and verbs.APPROVE or verbs.DECLINE,
            action_object=instance, target=instance.project
        )
