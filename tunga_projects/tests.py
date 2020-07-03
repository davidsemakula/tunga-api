# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from rest_framework import status

from tunga_projects.utils import get_every_other_monday
from tunga_utils.constants import USER_TYPE_PROJECT_MANAGER, \
    USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER


def test_every_other_monday_helper():
    date = datetime(2020, 3, 12)

    first_monday = datetime(2020, 3, 2)
    next_monday_1 = datetime(2020, 3, 9)  # monday to skip
    next_monday_2 = datetime(2020, 3, 16)
    next_monday_3 = datetime(2020, 3, 23)  # monday to skip
    next_monday_4 = datetime(2020, 3, 30)

    expected_mondays = get_every_other_monday(date)

    assert first_monday in expected_mondays
    assert next_monday_1 not in expected_mondays
    assert next_monday_2 in expected_mondays
    assert next_monday_3 not in expected_mondays
    assert next_monday_4 in expected_mondays


@pytest.mark.django_db
def test_create_project(client):
    project_owner = get_user_model().objects.create_user(
        'project_owner', 'po@example.com', 'secret',
        **dict(type=USER_TYPE_PROJECT_OWNER)
    )
    developer = get_user_model().objects.create_user(
        'developer', 'developer@example.com', 'secret',
        **dict(type=USER_TYPE_DEVELOPER)
    )
    project_manager = get_user_model().objects.create_user(
        'project_manager', 'pm@example.com', 'secret',
        **dict(type=USER_TYPE_PROJECT_MANAGER)
    )
    admin = get_user_model().objects.create_superuser(
        'admin', 'admin@example.com', 'secret'
    )

    project_data = {
        'category': 'project',
        'description': 'this is text',
        'expected_duration': '6m',
        'title': 'New project'

    }
    url = reverse('project-list')

    # developer can't create projects
    client.login(email=developer.email, password='secret')
    response = client.post(url, project_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # pms can create projects
    client.login(email=project_manager.email, password='secret')
    response = client.post(url, project_data)
    assert response.status_code == status.HTTP_201_CREATED

    # admin can create projects
    client.login(email=admin.email, password='secret')
    response = client.post(url, project_data)
    assert response.status_code == status.HTTP_201_CREATED

    # project owner's can't create projects
    client.login(email=project_owner.email, password='secret')
    response = client.post(url, project_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
