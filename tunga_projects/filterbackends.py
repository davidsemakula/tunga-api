from django.db.models import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_utils.constants import STATUS_INITIAL, STATUS_ACCEPTED, \
    STATUS_INTERESTED, PROJECT_STAGE_OPPORTUNITY
from tunga_utils.filterbackends import dont_filter_staff_or_superuser


class ProjectFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(
            Q(user=request.user) |
            Q(pm=request.user) |
            Q(owner=request.user) |
            (
                Q(participation__user=request.user) &
                Q(participation__status__in=[STATUS_INITIAL, STATUS_ACCEPTED])
            ) |
            (
                Q(stage=PROJECT_STAGE_OPPORTUNITY)
            )
        ).distinct()
