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
        'last_name': user.last_name,
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
    sso_create_user_endpoint = SSO_TOKEN_URL + "users/%s/change_password/" % user.sso_uuid
    headers = {
        'Authorization': "Bearer %s" % get_sso_access_token(user)
    }
    response = requests.post(sso_create_user_endpoint, data=pay_load,
                             headers=headers)
    if response.status_code == HTTP_200_OK:
        return True
    return False


def update_sso_user_details(user_profile, data):
    user_details = {
        "first_name": data.get('first_name'),
        "last_name": data.get('first_name'),
        "country": data.get('country'),
        "zip_code": data.get('postal_code'),
        "city": data.get('city'),
        "street": data.get('street'),
        "phone_number": data.get('phone_number'),

    }
    headers = {
        'Authorization': "Bearer %s" % get_sso_access_token(user_profile.user)
    }

    sso_update_user_endpoint = SSO_TOKEN_URL + "users/%s/" % user_profile.user.sso_uuid
    update_user_response = requests.patch(sso_update_user_endpoint,
                                          data=user_details,
                                          headers=headers)
    if update_user_response.status_code == HTTP_200_OK:
        return True
    return False


def update_platform_user_details(user):
    headers = {
        'Authorization': "Bearer %s" % get_sso_access_token(user)
    }

    sso_user_details_endpoint = SSO_TOKEN_URL + "users/%s/" % user.sso_uuid
    sso_user_details_response = requests.get(sso_user_details_endpoint,
                                             headers=headers)
    if sso_user_details_response.status_code == HTTP_200_OK:
        user_details = sso_user_details_response.json()
        user.profile.country = user_details.get('country')
        user.profile.postal_code = user_details.get('zip_code')
        user.profile.phone_number = user_details.get('phone_number')
        user.profile.city = user_details.get('city')
        user.profile.street = user_details.get('street')
        user.save()

    return None


def set_sso_user_password(user, new_password):
    pay_load = {
        'new_password': new_password,
    }
    sso_create_user_endpoint = SSO_TOKEN_URL + "users/%s/set_password/" % user.sso_uuid
    headers = {
        'Authorization': "Bearer %s" % get_sso_access_token(user)
    }
    response = requests.post(sso_create_user_endpoint, data=pay_load,
                             headers=headers)
    if response.status_code == HTTP_200_OK:
        return True
    return False


def check_if_users_exists_in_sso(current_user, email):
    sso_filter_user_by_email_endpoint = SSO_TOKEN_URL + "users/?email=%s" % requests.utils.quote(
        email)
    headers = {
        'Authorization': "Bearer %s" % get_sso_access_token(current_user)
    }
    response = requests.get(sso_filter_user_by_email_endpoint, headers=headers)
    if response.status_code == HTTP_200_OK:
        return True
    return False


def change_user_access_in_sso(current_user, email, platform_role):
    sso_filter_user_by_email_endpoint = SSO_TOKEN_URL + "users/?email=%s" % requests.utils.quote(
        email)
    headers = {
        'Authorization': "Bearer %s" % get_sso_access_token(current_user)
    }
    response = requests.get(sso_filter_user_by_email_endpoint, headers=headers)
    if response.status_code == HTTP_200_OK:
        response_data = response.json()
        count = response_data['count']
        if count > 0:
            uuid = response_data['results'][0]['id']
            sso_update_user_endpoint = SSO_TOKEN_URL + "users/%s/" % uuid
            payload = {
                'access': ['platform', 'developpp'],
                'platform_role': platform_role
            }
            update_user_response = requests.patch(sso_update_user_endpoint,
                                                  data=payload,
                                                  headers=headers)
            if update_user_response.status_code == HTTP_200_OK:
                return True
        else:
            return False

    return False


def get_sso_access_token(user):
    sso_refresh_token_endpoint = SSO_TOKEN_URL + "token/refresh/"
    pay_load = {
        'refresh': user.sso_refresh_token
    }
    response = requests.post(sso_refresh_token_endpoint, data=pay_load)
    if response.status_code == HTTP_200_OK:
        return response.json()['access']
    return ""
