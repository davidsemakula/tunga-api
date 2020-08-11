import datetime

import requests
from django.contrib.auth.backends import RemoteUserBackend
from django.shortcuts import get_object_or_404
from django.utils.deprecation import MiddlewareMixin

from tunga import settings
from tunga_auth.models import TungaUser


class UserLastActivityMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        try:
            if request.user.is_authenticated():
                request.user.last_activity_at = datetime.datetime.utcnow()
                request.user.save()
        except AttributeError:
            pass
        return response


class TungaSSORemoteUserBackend(RemoteUserBackend):
    """
    This is a call to the Tunga SSO service to check if this a remote user
    """

    def __init__(self, session=None):
        super(TungaSSORemoteUserBackend, self).__init__()
        # self.session = session if session else self._create_session()
        self.sso_base_url = settings.SSO_TOKEN_URL

    # @staticmethod
    # def _create_session():
    #     s = requests.Session()
    #     s.headers.update(
    #         {
    #             'accept': 'application/json',
    #             'Content-Type': 'application/json'
    #         }
    #     )
    #     return s

    def authenticate(self, request, username=None, password=None, **kwargs):
        api_url = self.sso_base_url + 'token/'
        data = {
            "username": username,
            "password": password
        }
        response = requests.post(url=api_url, data=data)
        if response.status_code == 200:
            username = response.json()['username']
            user = get_object_or_404(TungaUser, username=username)
            return user if self.user_can_authenticate(user) else None
        return None

    def get_user(self, user_id):
        try:
            return TungaUser.objects.get(pk=user_id)
        except TungaUser.DoesNotExist:
            return None
