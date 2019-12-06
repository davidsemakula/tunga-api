import datetime

from django.core.management.base import BaseCommand
from django.db.models.query_utils import Q

from tunga_projects.models import Project, ProgressEvent
from tunga_projects.notifications.generic import remind_progress_event
from tunga_utils.constants import STATUS_ACCEPTED, PROGRESS_EVENT_DEVELOPER, \
    PROGRESS_EVENT_PM, PROGRESS_EVENT_CLIENT, \
    PROGRESS_EVENT_MILESTONE, PROGRESS_EVENT_INTERNAL


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Schedule progress updates and send update reminders
        """
        # command to run: python manage.py tunga_manage_progress_updates

        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0,
                                                         second=0,
                                                         microsecond=0)
        today_noon = datetime.datetime.utcnow().replace(hour=12, minute=0,
                                                        second=0, microsecond=0)
        today_end = datetime.datetime.utcnow().replace(hour=23, minute=59,
                                                       second=59,
                                                       microsecond=999999)

        projects = Project.objects.filter(
            Q(deadline__isnull=True) | Q(deadline__gte=today_start),
            archived=False
        )
        for project in projects:

            all_milestones = ProgressEvent.objects.filter(
                project=project,
                type__in=[PROGRESS_EVENT_MILESTONE, PROGRESS_EVENT_INTERNAL],
                due_at__range=[today_start, today_end]
            )

            general_milestones = []  # For all stakeholders
            internal_milestones = []  # Only for PMs

            for milestone in all_milestones:
                # Send reminders for milestones
                if not milestone.last_reminder_at:
                    remind_progress_event.delay(milestone.id)

                # Filter milestone types
                if milestone.type == PROGRESS_EVENT_MILESTONE:
                    general_milestones.append(milestone)
                elif milestone.type == PROGRESS_EVENT_INTERNAL:
                    internal_milestones.append(milestone)

            if not general_milestones:
                # Automatic updates are only scheduled if no general milestone falls on this date
                weekday = today_noon.weekday()

                # participants with update on all weekdays
                participants = project.participation_set.filter(
                    status=STATUS_ACCEPTED, updates_enabled=True,
                    day_selection_for_updates=False)
                if weekday < 5 and participants:
                    # Only developer updates btn Monday (0) and Friday (4)
                    dev_defaults = dict(title='Developer Update')
                    dev_event, created = ProgressEvent.objects.update_or_create(
                        project=project, type=PROGRESS_EVENT_DEVELOPER,
                        due_at=today_noon, defaults=dev_defaults
                    )

                    if not dev_event.last_reminder_at:
                        remind_progress_event.delay(dev_event.id)

                # participants with update on specific days
                participants_ = project.participation_set.filter(
                    status=STATUS_ACCEPTED, updates_enabled=True,
                    day_selection_for_updates=True)
                if participants:
                    # Only developer updates specific days
                    for participant in participants:
                        if str(weekday) in participant.update_days.split(','):
                            dev_defaults = dict(title='Developer Update')
                            dev_event, created = ProgressEvent.objects.update_or_create(
                                project=project, type=PROGRESS_EVENT_DEVELOPER,
                                due_at=today_noon, defaults=dev_defaults
                            )

                            if not dev_event.last_reminder_at:
                                remind_progress_event.delay(dev_event.id)

                if weekday in [0,
                               3] and project.pm and project.pm.is_active and not internal_milestones:
                    # PM Reports on Monday (0) and Thursday (3)
                    pm_defaults = dict(title='PM Report')
                    pm_event, created = ProgressEvent.objects.update_or_create(
                        project=project, type=PROGRESS_EVENT_PM,
                        due_at=today_noon, defaults=pm_defaults
                    )
                    if not pm_event.last_reminder_at:
                        remind_progress_event.delay(pm_event.id)

                owner = project.owner or project.user
                if weekday == 0 and participants and owner and owner.is_active:
                    # Client surveys on Monday (0)
                    client_defaults = dict(title='Client Survey')
                    client_event, created = ProgressEvent.objects.update_or_create(
                        project=project, type=PROGRESS_EVENT_CLIENT,
                        due_at=today_noon, defaults=client_defaults
                    )
                    if not client_event.last_reminder_at:
                        remind_progress_event.delay(client_event.id)
