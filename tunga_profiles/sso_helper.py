import requests
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED

from tunga.settings import SSO_TOKEN_URL
from tunga_utils.constants import USER_TYPE_DEVELOPER, \
    USER_TYPE_PROJECT_MANAGER, USER_TYPE_PROJECT_OWNER

DEVELOPPP_TEST_CONTRIBUTOR = 2


def sync_user_sso(user, password):
    testing_role = USER_TYPE_DEVELOPER
    if user.type == USER_TYPE_PROJECT_MANAGER or user.type == USER_TYPE_PROJECT_OWNER:
        testing_role = DEVELOPPP_TEST_CONTRIBUTOR

    user_data = {
        'first_name': user.first_name,
        'last_name': user.first_name,
        'username': user.username,
        'email': user.email,
        'password': password,
        'platform_role': user.type,
        'developpp_role': testing_role,
        'access': [
            'platform', 'developpp'
        ]

    }

    sso_create_user_endpoint = SSO_TOKEN_URL + "users/"
    response = requests.post(sso_create_user_endpoint, data=user_data)
    if response.status_code == HTTP_201_CREATED:
        sso_uuid = response.json()['id']
        user.sso_uuid = sso_uuid
        user.save()


def change_sso_user_password(user, old_password, new_password):
    pay_load = {
        'old_password': old_password,
        'new_password': new_password,
    }
    sso_create_user_endpoint = SSO_TOKEN_URL + "users/%s/set_password/" % user.sso_uuid
    response = requests.post(sso_create_user_endpoint, data=pay_load)
    if response.status_code == HTTP_200_OK:
        return True
    return False
