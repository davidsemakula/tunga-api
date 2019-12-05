from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga_activity.models import FieldChangeLog
from tunga_projects.models import Project, Participation, Document, \
    ProgressEvent, ProjectMeta, ProgressReport, \
    InterestPoll, DeveloperRating
from tunga_projects.tasks import complete_exact_sync
from tunga_utils.constants import PROGRESS_REPORT_STATUS_CHOICES, \
    PROGRESS_REPORT_STATUS_STUCK, \
    PROGRESS_REPORT_STUCK_REASON_CHOICES, \
    PROGRESS_REPORT_STATUS_BEHIND_AND_STUCK
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.serializers import ContentTypeAnnotatedModelSerializer, \
    CreateOnlyCurrentUserDefault, \
    NestedModelSerializer, SimplestUserSerializer, SimpleModelSerializer, \
    SimpleSkillSerializer
from tunga_utils.signals import post_field_update
from tunga_utils.validators import validate_field_schema


class SimpleProjectSerializer(SimpleModelSerializer):
    skills = SimpleSkillSerializer(required=False, many=True)

    class Meta:
        model = Project
        fields = (
            'id', 'title', 'description', 'type', 'category',
            'expected_duration',
            'budget', 'currency', 'closed', 'start_date', 'deadline',
            'archived', 'skills'
        )


class NestedProjectSerializer(SimpleModelSerializer):
    user = SimplestUserSerializer(required=False, read_only=True)
    owner = SimplestUserSerializer(required=False, read_only=True)
    pm = SimplestUserSerializer(required=False, read_only=True)

    class Meta:
        model = Project
        fields = '__all__'


class SimpleParticipationSerializer(SimpleModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    user = SimplestUserSerializer()

    class Meta:
        model = Participation
        exclude = ('project',)


class SimpleInterestPollSerializer(SimpleModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    user = SimplestUserSerializer()

    class Meta:
        model = InterestPoll
        exclude = ('project',)


class SimpleDocumentSerializer(SimpleModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    download_url = serializers.CharField(read_only=True)

    class Meta:
        model = Document
        exclude = ('project',)


class SimpleProgressEventSerializer(SimpleModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = ProgressEvent
        exclude = ('project',)


class NestedProgressEventSerializer(SimpleModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    project = SimpleProjectSerializer(required=False, read_only=True)

    class Meta:
        model = ProgressEvent
        fields = '__all__'


class SimpleProgressReportSerializer(SimpleModelSerializer):
    user = SimplestUserSerializer(required=False, read_only=True,
                                  default=CreateOnlyCurrentUserDefault())
    status_display = serializers.CharField(required=False, read_only=True,
                                           source='get_status_display')
    stuck_reason_display = serializers.CharField(required=False, read_only=True,
                                                 source='get_stuck_reason_display')

    class Meta:
        model = ProgressReport
        exclude = ('event',)


class SimpleProjectMetaSerializer(SimpleModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = ProjectMeta
        exclude = ('project',)


class ProjectSerializer(
    NestedModelSerializer, ContentTypeAnnotatedModelSerializer,
    GetCurrentUserAnnotatedSerializerMixin
):
    user = SimplestUserSerializer(required=False, read_only=True,
                                  default=CreateOnlyCurrentUserDefault())
    owner = SimplestUserSerializer(required=False, allow_null=True)
    pm = SimplestUserSerializer(required=False, allow_null=True)
    skills = SimpleSkillSerializer(required=False, many=True)
    participation = SimpleParticipationSerializer(required=False, many=True,
                                                  source='participation_set')
    documents = SimpleDocumentSerializer(required=False, many=True,
                                         source='document_set')
    progress_events = SimpleProgressEventSerializer(required=False, many=True,
                                                    source='progressevent_set')
    meta = SimpleProjectMetaSerializer(required=False, many=True,
                                       source='projectmeta_set')
    change_log = serializers.JSONField(required=False, write_only=True)
    margin = serializers.ReadOnlyField()
    interest_polls = SimpleInterestPollSerializer(required=False, many=True,
                                                  source='interestpoll_set')
    expected_duration = serializers.CharField(required=True, read_only=False,
                                              allow_null=False,
                                              allow_blank=False)
    category = serializers.CharField(required=True, read_only=False,
                                     allow_null=False, allow_blank=False)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def nested_save_override(self, validated_data, instance=None):
        initial_stage = None
        initial_archived = None

        if instance:
            initial_stage = instance.stage
            initial_archived = instance.archived

        instance = super(ProjectSerializer, self).nested_save_override(
            validated_data, instance=instance)

        if instance:
            if initial_stage != instance.stage:
                post_field_update.send(sender=Project, instance=instance,
                                       field='stage')

            if type(
                initial_archived) == bool and instance.archived and not initial_archived:
                complete_exact_sync.delay(instance.id)

        return instance

    def save_nested_skills(self, data, instance, created=False):
        if data is not None:
            instance.skills = ', '.join(
                [skill.get('name', '') for skill in data])
            instance.save()

    def save_nested_change_log(self, data, instance, created=False):
        if data is not None:
            for item in data:
                FieldChangeLog.objects.create(content_object=instance,
                                              created_by=self.get_current_user(),
                                              **item)


class ParticipationSerializer(NestedModelSerializer,
                              ContentTypeAnnotatedModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    project = SimpleProjectSerializer()
    user = SimplestUserSerializer()

    class Meta:
        model = Participation
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class InterestPollSerializer(NestedModelSerializer,
                             ContentTypeAnnotatedModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    project = SimpleProjectSerializer()
    user = SimplestUserSerializer()

    class Meta:
        model = InterestPoll
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def nested_save_override(self, validated_data, instance=None):
        initial_status = None
        initial_approval_status = None

        if instance:
            initial_status = instance.status
            initial_approval_status = instance.approval_status

        instance = super(InterestPollSerializer, self).nested_save_override(
            validated_data, instance=instance)

        if instance:
            if initial_status != instance.status:
                post_field_update.send(sender=InterestPoll, instance=instance,
                                       field='status')
            if initial_approval_status != instance.approval_status:
                post_field_update.send(sender=InterestPoll, instance=instance,
                                       field='approval_status')
        return instance


class DocumentSerializer(NestedModelSerializer,
                         ContentTypeAnnotatedModelSerializer):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    project = SimpleProjectSerializer()
    download_url = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class ProgressEventSerializer(NestedModelSerializer,
                              ContentTypeAnnotatedModelSerializer,
                              GetCurrentUserAnnotatedSerializerMixin):
    created_by = SimplestUserSerializer(required=False, read_only=True,
                                        default=CreateOnlyCurrentUserDefault())
    project = SimpleProjectSerializer()
    progress_reports = SimpleProgressReportSerializer(
        required=False, read_only=True, many=True, source='progressreport_set'
    )
    change_log = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = ProgressEvent
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def save_nested_change_log(self, data, instance, created=False):
        if data is not None:
            for item in data:
                FieldChangeLog.objects.create(content_object=instance,
                                              created_by=self.get_current_user(),
                                              **item)


class ProgressReportSerializer(NestedModelSerializer,
                               ContentTypeAnnotatedModelSerializer,
                               GetCurrentUserAnnotatedSerializerMixin):
    user = SimplestUserSerializer(required=False, read_only=True,
                                  default=CreateOnlyCurrentUserDefault())
    event = NestedProgressEventSerializer()
    status_display = serializers.CharField(required=False, read_only=True,
                                           source='get_status_display')
    stuck_reason_display = serializers.CharField(required=False, read_only=True,
                                                 source='get_stuck_reason_display')

    class Meta:
        model = ProgressReport
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, attrs):
        errors = dict()

        current_user = self.get_current_user()
        if current_user.is_authenticated():
            BOOLEANS = (True, False)
            required_fields = []

            status_schema = (
                'status', [status_item[0] for status_item in
                           PROGRESS_REPORT_STATUS_CHOICES],
                [
                    (
                        [PROGRESS_REPORT_STATUS_BEHIND_AND_STUCK,
                         PROGRESS_REPORT_STATUS_STUCK],
                        'stuck_reason',
                        [stuck_reason_item[0] for stuck_reason_item in
                         PROGRESS_REPORT_STUCK_REASON_CHOICES]
                    )
                ]
            )
            rate_deliverables_schema = (
                'rate_deliverables', list(range(1, 6)))  # 1...5

            if current_user.is_developer:
                required_fields = [
                    status_schema,
                    'started_at',
                    ('percentage', list(range(0, 101))),  # 0...100
                    'accomplished',
                    rate_deliverables_schema,
                    'todo',
                    'next_deadline',
                    (
                        'next_deadline_meet', BOOLEANS,
                        [
                            (False, 'next_deadline_fail_reason')
                        ]
                    )
                ]
            elif current_user.is_project_manager:
                required_fields = [
                    status_schema,
                    (
                        'last_deadline_met', BOOLEANS,
                        [
                            (False, 'deadline_miss_communicated', BOOLEANS),
                            (False, 'deadline_report')
                        ]
                    ),
                    'percentage', 'accomplished', 'todo',
                    'next_deadline',
                    (
                        'next_deadline_meet', BOOLEANS,
                        [
                            (False, 'next_deadline_fail_reason')
                        ]
                    ),
                    'team_appraisal'
                ]
            elif current_user.is_project_owner:
                required_fields = [
                    (
                        'last_deadline_met', BOOLEANS,
                        [
                            (False, 'deadline_miss_communicated', BOOLEANS)
                        ]
                    ),
                    ('deliverable_satisfaction', BOOLEANS),
                    rate_deliverables_schema,
                    ('pm_communication', BOOLEANS)
                ]

            errors.update(validate_field_schema(required_fields, attrs,
                                                raise_exception=False))

        if errors:
            raise ValidationError(errors)
        return attrs


class DeveloperRatingSerializer(NestedModelSerializer,
                                ContentTypeAnnotatedModelSerializer,
                                GetCurrentUserAnnotatedSerializerMixin):
    user = SimplestUserSerializer(required=False, read_only=True,
                                  default=CreateOnlyCurrentUserDefault())
    event = NestedProgressEventSerializer()

    class Meta:
        model = DeveloperRating
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
