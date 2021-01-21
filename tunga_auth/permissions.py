from rest_framework import permissions
from rest_framework.permissions import IsAdminUser, SAFE_METHODS, IsAuthenticated

from tunga_auth.utils import get_session_visitor_email
from tunga_utils.constants import USER_TYPE_PROJECT_MANAGER


class IsAuthenticatedOrEmailVisitorReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS and get_session_visitor_email(request):
            return True
        return IsAuthenticated().has_permission(request, view)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsAdminUser().has_permission(request, view)


class IsAdminOrCreateOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return True
        return IsAdminUser().has_permission(request, view)


class IsPmOrIsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        is_pm = request.user.type == USER_TYPE_PROJECT_MANAGER
        return is_pm or IsAdminUser().has_permission(request, view)
