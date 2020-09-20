from django.core.management.base import BaseCommand

from tunga_auth.models import TungaUser
from tunga_utils import algolia_utils
from tunga_utils.constants import USER_TYPE_DEVELOPER
from tunga_utils.serializers import SearchUserSerializer


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Tunga Alogia Developer Export
        """
        # command to run: python manage.py tunga_algolia_export_developers

        users = TungaUser.objects.filter(type=USER_TYPE_DEVELOPER, is_active=True)

        algolia_utils.add_objects(SearchUserSerializer(users, many=True).data)
