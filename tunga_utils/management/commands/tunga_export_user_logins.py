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
        row = ['Email', 'Username', 'User Role',
               'Last Login', 'isActive', 'First Name', 'Last Name'
               ]
        with open('TungaUser.csv', 'a') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(row)

            for user in users:
                writer.writerow([user.email, user.username,
                                 user_type.get(user.type, None),
                                 user.last_login, user.is_active,
                                 user.first_name, user.last_name
                                 ])
        csvFile.close()
