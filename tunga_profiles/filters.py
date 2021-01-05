from tunga_profiles.models import Education, Work, Connection, ProfileProject,\
    DeveloperApplication, DeveloperInvitation
from tunga_utils.filters import GenericDateFilterSet


class EducationFilter(GenericDateFilterSet):
    class Meta:
        model = Education
        fields = ('institution', 'award')


class WorkFilter(GenericDateFilterSet):
    class Meta:
        model = Work
        fields = ('company', 'position')


class ProfileProjectFilter(GenericDateFilterSet):
    class Meta:
        model = ProfileProject
        fields = ('title', 'category')


class ConnectionFilter(GenericDateFilterSet):
    class Meta:
        model = Connection
        fields = ('from_user', 'to_user', 'status')


class DeveloperApplicationFilter(GenericDateFilterSet):
    class Meta:
        model = DeveloperApplication
        fields = ('status', 'used')


class DeveloperInvitationFilter(GenericDateFilterSet):
    class Meta:
        model = DeveloperInvitation
        fields = ('used',)
