import datetime

import requests
from django.contrib.auth.backends import RemoteUserBackend
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.deprecation import MiddlewareMixin
from rest_framework import status
from rest_framework.response import Response

from tunga import settings
from tunga_auth.models import TungaUser
from tunga_utils.constants import USER_TYPE_DEVELOPER


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
        self.sso_base_url = settings.SSO_TOKEN_URL

    def authenticate(self, request, username=None, password=None, **kwargs):

        no_access_message = "You have not been given access to the Tunga works platform yet.\
         Please ensure you have completed all required tests and then contact\
          Tunga staff to grant you access."

        api_url = self.sso_base_url + 'token/'
        data = {
            "username": username,
            "password": password
        }
        response = requests.post(url=api_url, data=data)
        if response.status_code == 200:
            response_data = response.json()
            refresh_token = response_data['refresh']
            platform_access = response_data['platform_access']
            if 'platform' in platform_access:
                user, created = TungaUser.objects.get_or_create(
                    username=response_data.get('username'),
                    defaults={
                        'email': response_data.get('email'),
                        'sso_uuid': response_data.get('id'),
                        'sso_refresh_token': refresh_token,
                        'first_name': response_data.get('first_name'),
                        'last_name': response_data.get('last_name'),
                        'is_active': True,
                        'type': USER_TYPE_DEVELOPER,
                        'verified': True
                    })

                user.sso_refresh_token = refresh_token
                user.set_password(password)
                user.sso_uuid = response_data.get('id')
                user.save()

                return user if self.user_can_authenticate(user) else None
            else:
                raise ValidationError(no_access_message)
        return None

    def get_user(self, user_id):
        try:
            return TungaUser.objects.get(pk=user_id)
        except TungaUser.DoesNotExist:
            return None
