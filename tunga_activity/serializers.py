from actstream.models import Action
from django.contrib.auth import get_user_model
from generic_relations.relations import GenericRelatedField
from rest_framework import serializers

from tunga_activity.models import ActivityReadLog, FieldChangeLog, NotificationReadLog
from tunga_comments.models import Comment
from tunga_comments.serializers import CommentSerializer
from tunga_messages.models import Message, Channel, ChannelUser
from tunga_messages.serializers import MessageSerializer, ChannelSerializer, ChannelUserSerializer
from tunga_payments.models import Invoice, Payment
from tunga_payments.serializers import InvoiceSerializer, PaymentSerializer
from tunga_profiles.models import Connection
from tunga_profiles.serializers import ConnectionSerializer
from tunga_projects.models import Project, Document, Participation, ProgressEvent, ProgressReport
from tunga_projects.serializers import ProjectSerializer, DocumentSerializer, ParticipationSerializer, \
    ProgressEventSerializer, ProgressReportSerializer
from tunga_tasks.models import Task, Application, Participation as LegacyParticipation, Integration, ProgressEvent as LegacyProgressEvent, ProgressReport as LegacyProgressReport, \
    IntegrationActivity, Estimate, Quote, Sprint
from tunga_tasks.serializers import ApplicationSerializer, ParticipationSerializer as LegacyParticipationSerializer, \
    SimpleTaskSerializer, SimpleIntegrationSerializer, SimpleProgressEventSerializer as LegacySimpleProgressEventSerializer, \
    SimpleProgressReportSerializer as LegacySimpleProgressReportSerializer, SimpleIntegrationActivitySerializer, ProgressReportSerializer as LegacyProgressReportSerializer, \
    SimpleEstimateSerializer, SimpleQuoteSerializer, SimpleSprintSerializer
from tunga_uploads.models import Upload
from tunga_uploads.serializers import UploadSerializer
from tunga_utils.models import Upload as LegacyUpload
from tunga_utils.serializers import SimpleUserSerializer, UploadSerializer as LegacyUploadSerializer, \
    SimplestUserSerializer, CreateOnlyCurrentUserDefault


class ActivityReadLogSerializer(serializers.ModelSerializer):

    class Meta:
        model = ActivityReadLog
        fields = '__all__'


class NotificationReadLogSerializer(serializers.ModelSerializer):
    user = SimplestUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = NotificationReadLog
        fields = '__all__'


class LastReadActivitySerializer(serializers.Serializer):
    last_read = serializers.IntegerField(required=True)


class FieldChangeLogSerializer(serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField()
    target = GenericRelatedField({
        Project: ProjectSerializer(),
        ProgressEvent: ProgressEventSerializer(),
    }, source='content_object')
    created_by = SimplestUserSerializer()

    class Meta:
        model = FieldChangeLog
        fields = '__all__'

    def get_target_type(self, obj):
        return get_instance_type(obj.content_object)


class SimpleActivitySerializer(serializers.ModelSerializer):
    action = serializers.CharField(source='verb')
    activity_type = serializers.SerializerMethodField()
    activity = GenericRelatedField({
        get_user_model(): SimpleUserSerializer(),
        Channel: ChannelSerializer(),
        ChannelUser: ChannelUserSerializer(),
        Message: MessageSerializer(),
        Comment: CommentSerializer(),
        LegacyUpload: LegacyUploadSerializer(),
        Connection: ConnectionSerializer(),
        Task: SimpleTaskSerializer(),
        Application: ApplicationSerializer(),
        LegacyParticipation: LegacyParticipationSerializer(),
        Estimate: SimpleEstimateSerializer(),
        Quote: SimpleQuoteSerializer(),
        Sprint: SimpleSprintSerializer(),
        LegacyProgressEvent: LegacySimpleProgressEventSerializer(),
        LegacyProgressReport: LegacyProgressReportSerializer(),
        Integration: SimpleIntegrationSerializer(),
        IntegrationActivity: SimpleIntegrationActivitySerializer(),
        Project: ProjectSerializer(),
        Document: DocumentSerializer(),
        Participation: ParticipationSerializer(),
        ProgressEvent: ProgressEventSerializer(),
        ProgressReport: ProgressReportSerializer(),
        Invoice: InvoiceSerializer(),
        Payment: PaymentSerializer(),
        Upload: UploadSerializer(),
        FieldChangeLog: FieldChangeLogSerializer(),
    }, source='action_object')

    class Meta:
        model = Action
        exclude = (
            'verb', 'actor_object_id', 'actor_content_type', 'action_object_object_id', 'action_object_content_type',
            'target_object_id', 'target_content_type'
        )

    def get_activity_type(self, obj):
        return get_instance_type(obj.action_object)


class ActivitySerializer(SimpleActivitySerializer):
    actor_type = serializers.SerializerMethodField()
    target_type = serializers.SerializerMethodField()

    class Meta(SimpleActivitySerializer.Meta):
        fields = '__all__'
        exclude = None

    def get_actor_type(self, obj):
        return get_instance_type(obj.actor)

    def get_target_type(self, obj):
        return get_instance_type(obj.target)


def get_instance_type(instance):
    if instance:
        instance_class = type(instance)
        is_legacy = instance_class in [LegacyProgressEvent, LegacyProgressReport, LegacyUpload, LegacyParticipation]
        return to_snake_case(str('{}{}'.format(is_legacy and 'Legacy' or '', instance_class.__name__)))
    return None


def to_snake_case(components):
    return (components[0] + "".join(x.isupper() and '_{}'.format(x) or x for x in components[1:])).lower()
