import json
import re
from decimal import Decimal
import os

import slackdown
from allauth.socialaccount.models import SocialToken
from django.apps import apps as django_apps
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.template.defaultfilters import urlizetrunc, safe, striptags
from django.utils import six
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from tunga import settings
from tunga_utils.constants import HEADER_EDIT_TOKEN


def get_tunga_model(model):
    """
    Returns the Model class.
    """
    try:
        return django_apps.get_model(model)
    except ValueError:
        raise ImproperlyConfigured(
            "Model must be of the form 'app_label.model_name'")
    except LookupError:
        raise ImproperlyConfigured("Model has not been installed")


def clean_instance(instance, model):
    if instance and model:
        if isinstance(instance, model):
            return instance
        else:
            try:
                return model.objects.get(id=instance)
            except:
                return None
    else:
        return None


def pdf_base64encode(pdf_filename):
    return open(pdf_filename, "rb").read().encode("base64")


def swagger_permission_denied_handler(request):
    return HttpResponseRedirect('%s://%s/api/login/?next=/api/docs/' % (
    request.scheme, request.get_host()))


class Echo(object):
    """An object that implements just the write method of the file-like
    interface.
    """

    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class GenericObject:
    def __init__(self, **kwargs):
        for k, v in six.iteritems(kwargs):
            setattr(self, k, type(v) == dict and GenericObject(**v) or v)


def get_social_token(user, provider):
    try:
        return SocialToken.objects.filter(account__user=user,
                                          account__provider=provider).latest(
            'expires_at')
    except SocialToken.DoesNotExist:
        return None


def convert_slack_to_html(body):
    try:
        return slackdown.render(body)
    except:
        return body


def convert_to_text(body):
    """
    Create plain text from html
    :param body:
    :return:
    """
    if not body:
        return body
    txt_body = re.sub(r'(<br\s*/\s*>|<\s*/\s*(?:div|p)>)', '\\1\n', body,
                      flags=re.IGNORECASE)
    txt_body = striptags(txt_body)  # Striptags
    txt_body = re.sub(r'&nbsp;', ' ', txt_body,
                      flags=re.IGNORECASE)  # Replace &nbsp; with space
    txt_body = re.sub(r' {2,}', ' ', txt_body,
                      flags=re.IGNORECASE)  # Squash all multi spaces
    txt_body = re.sub(r'\r\n', '\n', txt_body,
                      flags=re.IGNORECASE)  # single new line format
    txt_body = re.sub(r'\t', '\n', txt_body,
                      flags=re.IGNORECASE)  # Remove indents
    txt_body = re.sub(r'\n( )+', '\n', txt_body,
                      flags=re.IGNORECASE)  # Remove indents
    txt_body = re.sub(r'\n{3,}', '\n\n', txt_body,
                      flags=re.IGNORECASE)  # Limit consecutive new lines to a max of 2
    return txt_body


def convert_to_html(body):
    if not body:
        return body
    return safe(
        re.sub(
            r'<a([^>]+)>(?:http|ftp)s?://([^<]+)</a>',
            '<a\\1>\\2</a>',
            re.sub(
                r'<a([^>]+)(?<!target=)>',
                '<a target="_blank"\\1>',
                urlizetrunc(re.sub(r'(<br\s*/>)?\n', '<br/>', body,
                                   flags=re.IGNORECASE), limit=50,
                            autoescape=False),
                flags=re.IGNORECASE
            ),
            re.IGNORECASE
        )
    )


def round_decimal(number, ndigits):
    formatter = '{0:.%sf}' % ndigits
    return Decimal(formatter.format(Decimal(number)))


def get_serialized_id(number, max_digits=4):
    remainder_max_digits = number % (10 ** max_digits)
    divider_max_digits = (number // (10 ** max_digits))
    letters = convert_to_base_alphabet(divider_max_digits)
    return '{}{:04d}'.format(letters, remainder_max_digits)


def convert_to_base_alphabet(number):
    remainder_letters = number % 26
    divider_letters = number // 26

    last_letter = chr(ord('A') + remainder_letters)
    base_alphabet_string = last_letter

    if divider_letters > 0:
        base_alphabet_string = '{}{}'.format(
            convert_to_base_alphabet(divider_letters - 1), base_alphabet_string)
    return base_alphabet_string


def clean_meta_value(meta_value):
    if isinstance(meta_value, (str, unicode, int, float)):
        return meta_value
    elif isinstance(meta_value, dict):
        try:
            return json.dumps(meta_value)
        except:
            pass
    return str(meta_value)


def convert_to_emoji(value):
    value_emoji_dict = {
        1: ":angry:",
        2: ":confused:",
        3: ":neutral_face:",
        4: ":slightly_smiling_face:",
        5: ":grinning:",
    }
    return value_emoji_dict[value]


def get_edit_token_header(request):
    return request.META.get(HEADER_EDIT_TOKEN, None)


def save_to_google_sheet(sheet_id, data, index=1):
    """
    This saves to google sheet
    url: str -> url of the google sheet file
    index: number -> position where the data should be saved
    data: array -> post data
    """
    # use creds to create a client to interact with the Google Drive API
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        os.path.join(settings.BASE_DIR, 'tunga', 'env', 'credentials.json'),
        scope
    )
    client = gspread.authorize(credentials)

    # Make sure you use the right name here.
    sheet = client.open_by_key(sheet_id).sheet1
    sheet.insert_row(data, index)
    return sheet
