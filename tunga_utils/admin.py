from django.contrib import admin

from tunga_utils.models import ContactRequest, SiteMeta, InviteRequest, ExternalEvent, SearchEvent


class AdminAutoCreatedBy(admin.ModelAdmin):
    exclude = ('created_by',)

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.save()


class ReadOnlyModelAdmin(admin.ModelAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        if not self.fields:
            return [
                field.name
                for field in self.model._meta.fields
                if field != self.model._meta.pk
            ]
        else:
            return self.fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if request.method not in ('GET', 'HEAD'):
            return False
        else:
            return super(ReadOnlyModelAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        pass


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ('fullname', 'email', 'item', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('email', 'fullname')


@admin.register(SiteMeta)
class SiteMetaAdmin(AdminAutoCreatedBy):
    list_display = ('meta_key', 'meta_value', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('meta_key',)


@admin.register(InviteRequest)
class InviteRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'country')
    list_filter = ('country',)
    search_fields = ('name', 'email')


@admin.register(ExternalEvent)
class ExternalEventAdmin(ReadOnlyModelAdmin):
    list_display = ('source', 'payload', 'created_at', 'notification_sent_at')
    list_filter = ('source',)
    search_fields = ('payload',)


@admin.register(SearchEvent)
class SearchEventAdmin(ReadOnlyModelAdmin):
    list_display = ('user_email', 'query', 'page', 'created_at', 'updated_at')
    search_fields = ('query', 'email', 'user__email')

    def user_email(self, obj):
        return obj.user_email

    user_email.empty_value_display = ''
    user_email.short_description = 'user email'

    def get_queryset(self, request):
        qs = super(SearchEventAdmin, self).get_queryset(request)
        all_events = SearchEvent.objects.order_by('created_at').all()
        print(all_events)
        allowed_ids = []
        seen_combos = []
        if all_events:
            for event in all_events:
                combo_name = '{}_{}_{}'.format(event.user and 'user' or 'guest', event.user_email, event.query)
                if combo_name not in seen_combos:
                    seen_combos.append(combo_name)
                    allowed_ids.append(event.id)
        return qs.filter(id__in=allowed_ids)
