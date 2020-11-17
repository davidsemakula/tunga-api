import csv

from tunga_auth.models import TungaUser
from django.core.management import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Migrate client invoices
        """
        # command to run: python manage.py tunga_export_developers
        USER_TYPE_DEVELOPER = 1
        USER_TYPE_PROJECT_OWNER = 2
        USER_TYPE_PROJECT_MANAGER = 3
        user_type = {
            USER_TYPE_DEVELOPER: "Developer",
            USER_TYPE_PROJECT_OWNER: "Project Owner",
            USER_TYPE_PROJECT_MANAGER: "Project Manager",
        }

        users = TungaUser.objects.filter(type=USER_TYPE_DEVELOPER,
                                         is_active=True).order_by('last_login')

        row = ["Date Joined", "First name", "Last Name", "Title", "Email",
               "Phone Number",
               "Street Name", "City", "Country", "Profile"]
        with open('tunga_developers.csv', 'a') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(row)

            for user in users:
                writer.writerow(
                    [user.date_joined.strftime('%d/%m/%Y'), user.first_name, user.last_name,
                     user.category,
                     user.email, user.phone_number,
                     user.profile.street if user.profile else "",
                     user.profile.city if user.profile else "",
                     user.profile.country.name if user.profile else "",
                     "https://tunga.io/dev-profile/%d" % user.id])
        csvFile.close()
