import csv

from tunga_auth.models import TungaUser
from django.core.management import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Migrate client invoices
        """
        # command to run: python manage.py tunga_export_user_logins
        USER_TYPE_DEVELOPER = 1
        USER_TYPE_PROJECT_OWNER = 2
        USER_TYPE_PROJECT_MANAGER = 3
        user_type = {
            USER_TYPE_DEVELOPER: "Developer",
            USER_TYPE_PROJECT_OWNER: "Project Owner",
            USER_TYPE_PROJECT_MANAGER: "Project Manager",
        }

        users = TungaUser.objects.all().order_by('last_login')
        row = ['First Name', ' Last Name', 'Email', 'Last Login', 'User Role']
        with open('TungaUser.csv', 'a') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(row)

            for user in users:
                writer.writerow([user.first_name, user.last_name, user.email,
                                 user.last_login,
                                 user_type.get(user.type, None)])

        csvFile.close()
