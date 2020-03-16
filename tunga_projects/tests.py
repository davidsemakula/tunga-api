# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime

from django.test import TestCase

# Create your tests here.
from tunga_projects.utils import get_every_other_monday


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
