from actstream.models import Action
from django.contrib.auth import get_user_model
from generic_relations.relations import GenericRelatedField
from rest_framework import serializers

from tunga_activity.models import ActivityReadLog
from tunga_comments.models import Comment
from tunga_comments.serializers import CommentSerializer
from tunga_messages.models import Message, Channel, ChannelUser
from tunga_messages.serializers import MessageSerializer, ChannelSerializer, ChannelUserSerializer
from tunga_payments.models import Invoice, Payment
from tunga_payments.serializers import InvoiceSerializer, PaymentSerializer
from tunga_profiles.models import Connection
from tunga_profiles.serializers import ConnectionSerializer
from tunga_projects.models import Project, Document, Participation, ProgressEvent
from tunga_projects.serializers import ProjectSerializer, DocumentSerializer, ParticipationSerializer, \
    ProgressEventSerializer
from tunga_tasks.models import Task, Application, Participation as LegacyParticipation, Integration, ProgressEvent as LegacyProgressEvent, ProgressReport, \
    IntegrationActivity, Estimate, Quote, Sprint
from tunga_tasks.serializers import ApplicationSerializer, ParticipationSerializer as LegacyParticipationSerializer, \
    SimpleTaskSerializer, SimpleIntegrationSerializer, SimpleProgressEventSerializer as LegacySimpleProgressEventSerializer, \
    SimpleProgressReportSerializer, SimpleIntegrationActivitySerializer, ProgressReportSerializer, \
    SimpleEstimateSerializer, SimpleQuoteSerializer, SimpleSprintSerializer
from tunga_utils.models import Upload
from tunga_utils.serializers import SimpleUserSerializer, UploadSerializer


class ActivityReadLogSerializer(serializers.Serializer):

    class Meta:
        model = ActivityReadLog
        fields = '__all__'


class LastReadActivitySerializer(serializers.Serializer):
    last_read = serializers.IntegerField(required=True)


class SimpleActivitySerializer(serializers.ModelSerializer):
    action = serializers.CharField(source='verb')
    activity_type = serializers.SerializerMethodField()
    activity = GenericRelatedField({
        get_user_model(): SimpleUserSerializer(),
        Channel: ChannelSerializer(),
        ChannelUser: ChannelUserSerializer(),
        Message: MessageSerializer(),
        Comment: CommentSerializer(),
        Upload: UploadSerializer(),
        Connection: ConnectionSerializer(),
        Task: SimpleTaskSerializer(),
        Application: ApplicationSerializer(),
        LegacyParticipation: LegacyParticipationSerializer(),
        Estimate: SimpleEstimateSerializer(),
        Quote: SimpleQuoteSerializer(),
        Sprint: SimpleSprintSerializer(),
        LegacyProgressEvent: LegacySimpleProgressEventSerializer(),
        ProgressReport: ProgressReportSerializer(),
        Integration: SimpleIntegrationSerializer(),
        IntegrationActivity: SimpleIntegrationActivitySerializer(),
        Project: ProjectSerializer(),
        Document: DocumentSerializer(),
        Participation: ParticipationSerializer(),
        ProgressEvent: ProgressEventSerializer(),
        Invoice: InvoiceSerializer(),
        Payment: PaymentSerializer()
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
    actor = GenericRelatedField({
        get_user_model(): SimpleUserSerializer(),
        Integration: SimpleIntegrationSerializer()
    })
    target = GenericRelatedField({
        get_user_model(): SimpleUserSerializer(),
        Channel: ChannelSerializer(),
        ChannelUser: ChannelUserSerializer(),
        Message: MessageSerializer(),
        Comment: CommentSerializer(),
        Upload: UploadSerializer(),
        Connection: ConnectionSerializer(),
        Task: SimpleTaskSerializer(),
        Application: ApplicationSerializer(),
        LegacyParticipation: LegacyParticipationSerializer(),
        LegacyProgressEvent: LegacySimpleProgressEventSerializer(),
        ProgressReport: SimpleProgressReportSerializer(),
        Integration: SimpleIntegrationSerializer(),
        IntegrationActivity: SimpleIntegrationActivitySerializer(),
        Project: ProjectSerializer(),
        Invoice: InvoiceSerializer()
    })

    class Meta(SimpleActivitySerializer.Meta):
        fields = '__all__'
        exclude = None

    def get_actor_type(self, obj):
        return get_instance_type(obj.actor)

    def get_target_type(self, obj):
        return get_instance_type(obj.target)


def get_instance_type(instance):
    if instance:
        return to_snake_case(str(type(instance).__name__))
    return None


def to_snake_case(components):
    return (components[0] + "".join(x.isupper() and '_{}'.format(x) or x for x in components[1:])).lower()
