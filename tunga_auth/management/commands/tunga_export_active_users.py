import csv

from django.core.management import BaseCommand

from tunga_auth.models import TungaUser


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Migrate client invoices
        """
        # command to run: python manage.py tunga_export_active_users
        USER_TYPE_DEVELOPER = 1
        USER_TYPE_PROJECT_OWNER = 2
        USER_TYPE_PROJECT_MANAGER = 3
        user_type = {
            USER_TYPE_DEVELOPER: "Developer",
            USER_TYPE_PROJECT_OWNER: "Project Owner",
            USER_TYPE_PROJECT_MANAGER: "Project Manager",
        }

        users = TungaUser.objects.filter(is_active=True)
        row = ['Date', 'Last Login', 'First Name', ' Last Name', 'Email',
               'Username', 'Role',
               'Active', 'Password']
        with open('tunga_users_active.csv', 'a') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(row)

            for user in users:
                writer.writerow(
                    [user.date_joined, user.last_login, user.first_name.encode(
                        'utf-8').strip(), user.last_name.encode(
                        'utf-8').strip(), user.email,
                     user.username,
                     user_type.get(user.type, None),
                     user.is_active, user.password])

        csvFile.close()
