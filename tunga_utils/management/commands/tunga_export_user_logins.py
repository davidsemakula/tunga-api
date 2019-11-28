import csv

from tunga_auth.models import TungaUser
from django.core.management import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Migrate client invoices
        """
        # command to run: python manage.py tunga_export_user_logins

        users = TungaUser.objects.all()
        row = ['First Name', ' Last Name', 'Email', 'Last Login']
        with open('TungaUser.csv', 'a') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(row)

            for user in users:
                writer.writerow([user.first_name, user.last_name, user.email, user.last_login])


        csvFile.close()
