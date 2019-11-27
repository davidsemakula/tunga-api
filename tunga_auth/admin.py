import csv

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.http.response import StreamingHttpResponse
from django.utils.translation import ugettext_lazy as _

from tunga_auth.forms import TungaUserChangeForm, TungaUserCreationForm
from tunga_auth.models import EmailVisitor, TungaUser
from tunga_utils.constants import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_profiles.admin import UserProfileInline, CompanyInline
from tunga_utils.helpers import Echo


@admin.register(get_user_model())
class TungaUserAdmin(UserAdmin):
    form = TungaUserChangeForm
    add_form = TungaUserCreationForm
    actions = UserAdmin.actions + ['make_pending', 'make_not_pending', 'download_csv']
    search_fields = ('first_name', 'last_name', 'email', 'invoice_email')

    fieldsets = UserAdmin.fieldsets + (
        (_('Profile'), {'fields': ('type', 'image', 'is_internal', 'can_pay', 'verified', 'pending', 'invoice_email')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Account Type'), {'fields': ('is_superuser', 'is_staff', 'type', 'source')}),
        (_('Profile'), {'fields': ('email', 'first_name', 'last_name', 'invoice_email')})
    )

    list_display = (
        'username', 'email', 'first_name', 'last_name', 'invoice_email',
        'is_staff', 'is_internal', 'can_pay', 'type', 'source', 'pending', 'verified', 'date_joined'
    )
    list_filter = ('date_joined', 'type', 'pending', 'is_staff', 'is_superuser', 'is_internal', 'payoneer_status')
    list_max_show_all = 1000

    inlines = (CompanyInline, UserProfileInline)

    def get_actions(self, request):
        # Disable delete
        actions = super(TungaUserAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False

    def make_pending(self, request, queryset):
        rows_updated = queryset.update(pending=True)
        self.message_user(
            request, "%s user%s successfully marked as pending." % (rows_updated, (rows_updated > 1 and 's' or '')))

    make_pending.short_description = "Mark selected users as pending"

    def make_not_pending(self, request, queryset):
        rows_updated = queryset.update(pending=False)
        self.message_user(
            request, "%s user%s successfully marked as active." % (rows_updated, (rows_updated > 1 and 's' or '')))

    make_not_pending.short_description = "Mark selected users as active"

    def download_csv(self, request, queryset):
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        query = dict()

        filter_type = request.GET.get('type__exact', None)
        b = request.POST
        for key in self.list_filter:
            field_filter = '{}__exact'.format(key)
            if field_filter in request.GET.keys():
                query[field_filter] = request.GET.get(field_filter)
        print(request.GET)

        report_header = [
            "First Name", "Last Name", "E-mail", "Phone Number", "User Type",
            "Company", "Country", "City", "Street", "Plot Number", "ZIP Code", "Postal Address",
            "VAT Number"
        ]

        if filter_type != str(USER_TYPE_DEVELOPER):
            report_header.append("Company Reg. Number")

        report_rows = [report_header]
        for user in self.model.objects.filter(**query):
            phone_number = user.profile and user.profile.phone_number or ""
            user_info = [
                user.first_name and user.first_name.encode('utf-8') or '',
                user.last_name and user.last_name.encode('utf-8') or '',
                user.email,
                "=\"%s\"" % phone_number,
                user.display_type,
                user.profile and user.profile.company or "",
                user.profile and user.profile.country_name or "",
                user.profile and user.profile.city_name or "",
                user.profile and user.profile.street or "",
                user.profile and user.profile.plot_number or "",
                user.profile and user.profile.postal_code or "",
                user.profile and user.profile.postal_address or "",
                user.profile and user.profile.vat_number or "",
            ]
            if filter_type != str(USER_TYPE_DEVELOPER):
                user_info.append(user.profile and user.profile.company_reg_no or "")
            report_rows.append(user_info)

        file_suffix = "users"
        if filter_type == str(USER_TYPE_DEVELOPER):
            file_suffix = "developers"
        elif filter_type == str(USER_TYPE_PROJECT_OWNER):
            file_suffix = "clients"

        response = StreamingHttpResponse((writer.writerow(row) for row in report_rows), content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename=tunga_%s.csv' % file_suffix
        return response

    download_csv.short_description = "Download CSV of selected users"


@admin.register(EmailVisitor)
class EmailVisitorAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at', 'last_login_at')
    list_filter = ('created_at', 'last_login_at')
    search_fields = ('email',)
    readonly_fields = ('email',)

    actions = ['download_csv']

    def download_csv(self, request, queryset):
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        report_header = ["E-mail"]

        report_rows = [report_header]
        for user in queryset:
            if TungaUser.objects.filter(email=user.email).count() == 0:
                user_info = [
                    user.email
                ]
                report_rows.append(user_info)

        response = StreamingHttpResponse((writer.writerow(row) for row in report_rows), content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename=tunga_email_visitors.csv'
        return response

    download_csv.short_description = "Download CSV of selected users"
