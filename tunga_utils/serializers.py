# -*- coding: utf-8 -*-
from collections import OrderedDict

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import six
from django_countries.serializer_fields import CountryField
from rest_framework import serializers
from rest_framework.fields import SkipField

from tunga_profiles.models import Skill, City, UserProfile, Education, Work, \
    Connection, BTCWallet, Company, ProfileProject
from tunga_profiles.utils import profile_check
from tunga_tasks.models import TaskInvoice
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.models import GenericUpload, ContactRequest, Upload, AbstractExperience, Rating, InviteRequest
from tunga_utils.signals import post_nested_save


class CreateOnlyCurrentUserDefault(serializers.CurrentUserDefault):

    def set_context(self, serializer_field):
        self.is_update = serializer_field.parent and serializer_field.parent.instance is not None
        super(CreateOnlyCurrentUserDefault, self).set_context(serializer_field)

    def __call__(self):
        if hasattr(self, 'is_update') and self.is_update:
            # TODO: Make sure this check is sufficient for all update scenarios
            raise SkipField()
        user = super(CreateOnlyCurrentUserDefault, self).__call__()
        if user and user.is_authenticated():
            return user
        return None


class SimpleModelSerializer(serializers.ModelSerializer):

    def to_internal_value(self, data):
        object_id = data.get('id', None)
        if object_id:
            if len(data) == 1:
                rep = self.Meta.model.objects.get(pk=object_id)
            else:
                #data.pop('id')
                rep = super(SimpleModelSerializer, self).to_internal_value(data)
                rep['id'] = object_id
            return rep
        else:
            rep = super(SimpleModelSerializer, self).to_internal_value(data)
            for serializer_field, serializer_field_value in six.iteritems(self.get_fields()):
                # Process missing default values for nested inserts during top level patch requests
                default_value = getattr(serializer_field_value, 'default', None)
                if serializer_field not in rep and default_value and default_value is not serializers.empty:
                    if isinstance(default_value, object):
                        # If default_value is a class based validator (e.g CurrentUserDefault), process value correctly
                        default_validator = default_value
                        default_validator.set_context(serializer_field_value.__class__(context=self.context))
                        default_value = default_validator.__call__()
                    if default_value:
                        rep[serializer_field] = default_value
            return rep

    def create(self, validated_data):
        return self.simple_save_override(validated_data)

    def update(self, instance, validated_data):
        return self.simple_save_override(validated_data, instance=instance)

    def simple_save_override(self, validated_data, instance=None):
        object_id = None
        if instance:
            object_id = instance.id
        elif id in validated_data:
            object_id = validated_data[id]
        if object_id:
            instance = self.Meta.model.objects.filter(pk=object_id).update(**validated_data)
        else:
            instance = self.Meta.model.objects.create(**validated_data)
        return instance


class ContentTypeAnnotatedModelSerializer(serializers.ModelSerializer):
    content_type = serializers.SerializerMethodField(read_only=True, required=False)

    def get_content_type(self, obj):
        return ContentType.objects.get_for_model(self.Meta.model).id


class NestedModelSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        return self.nested_save_override(validated_data)

    def update(self, instance, validated_data):
        return self.nested_save_override(validated_data, instance=instance)

    def nested_save_override(self, validated_data, instance=None):
        nested_method_models = []
        nested_data = []

        field_source_map = dict()
        for field_key in self.get_fields():
            field_value = self.get_fields().get(field_key, None)
            if field_value:
                source = getattr(field_value, 'source', None)
                if source:
                    field_source_map[source] = field_key

        for attribute_key in self.validated_data.keys():
            clean_attribute_key = field_source_map.get(attribute_key, attribute_key)
            save_method = getattr(self, 'save_nested_{}'.format(clean_attribute_key), None)
            attribute_value = self.validated_data.get(attribute_key, None)
            if save_method:
                # Filter nested save model data
                if attribute_value:
                    nested_method_models.append((save_method, attribute_value))

                # remove attribute from validated data if it exists
                validated_data.pop(attribute_key)
            elif type(attribute_value) in [dict, list]:
                # Filter nested data
                serializer_field = self.get_fields().get(clean_attribute_key, None)
                if serializer_field:
                    serializer_field_child = getattr(serializer_field, 'child', None)

                    if serializer_field_child:
                        serializer_class = serializer_field_child.__class__
                    else:
                        serializer_class = serializer_field.__class__

                    if serializer_class:
                        fk_keys = []
                        if serializer_class.Meta and serializer_class.Meta.model and self.Meta and self.Meta.model:
                            for model_field in serializer_class.Meta.model._meta.get_fields():
                                if model_field.related_model == self.Meta.model:
                                    fk_keys.append(model_field.name)
                        if type(attribute_value) is list:
                            for single_attribute_value in attribute_value:
                                nested_data.append((clean_attribute_key, single_attribute_value, serializer_class, fk_keys))
                        else:
                            nested_data.append((clean_attribute_key, attribute_value, serializer_class, fk_keys))

                # remove attribute from validated data to prevent writable nested non readonly fields error
                validated_data.pop(attribute_key)

            if type(attribute_value) in [dict, OrderedDict]:
                attribute_value_object_id = attribute_value.get('id', None)
                if attribute_value_object_id:
                    serializer_field = self.get_fields().get(clean_attribute_key, None)
                    serializer_class = serializer_field.__class__
                    validated_data[clean_attribute_key] = serializer_class.Meta.model.objects.get(pk=attribute_value_object_id)

        is_created = not bool(instance)
        if instance:
            instance = super(NestedModelSerializer, self).update(instance, validated_data)
        else:
            instance = super(NestedModelSerializer, self).create(validated_data)

        try:
            # Saving nested values is best effort
            for attribute_details in nested_method_models:
                save_method = attribute_details[0]
                attribute_value = attribute_details[1]
                if save_method and attribute_value:
                    save_method(attribute_value, instance, created=is_created)

            for (k, v, s, r) in nested_data:
                v = dict(v)
                if r:
                    for related_key in r:
                        v[related_key] = instance
                if s.Meta.model:
                    if 'id' in v:
                        s.Meta.model.objects.update_or_create(id=v['id'], defaults=v)
                    else:
                        s.Meta.model.objects.create(**v)
                else:
                    serializer = s(data=v, **dict(context=self.context))
                    serializer.save()
        except:
            pass

        post_nested_save.send(sender=self.__class__.Meta.model, instance=instance, created=is_created)
        return instance


class DetailAnnotatedModelSerializer(serializers.ModelSerializer):
    details = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        details_serializer = None

    def get_details(self, obj):
        try:
            if self.Meta.details_serializer:
                return self.Meta.details_serializer(obj).data
        except AttributeError:
            return None


class SimpleSkillSerializer(SimpleModelSerializer):

    class Meta:
        model = Skill
        fields = ('id', 'name', 'slug', 'type')
        read_only_fields = ('slug',)

    def to_internal_value(self, data):
        return data


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ('id', 'name', 'slug', 'type')


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name', 'slug')


class SimpleBTCWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = BTCWallet
        exclude = ('token', 'token_secret')


class SkillsDetailsSerializer(serializers.Serializer):

    def to_representation(self, instance):
        json = dict()
        for category in instance:
            json[category] = SkillSerializer(instance=instance[category], many=True).data
        return json


class SimplestCompanySerializer(serializers.ModelSerializer):
    city = serializers.CharField(required=False)
    skills = SkillSerializer(many=True, required=False)
    country = CountryField(required=False)
    country_name = serializers.CharField(required=False)
    location = serializers.CharField(read_only=True)
    skills_details = SkillsDetailsSerializer(read_only=True)

    class Meta:
        model = Company
        exclude = ('user',)


class SimpleCompanySerializer(serializers.ModelSerializer):
    city = serializers.CharField()
    skills = SkillSerializer(many=True)
    country = CountryField()
    country_name = serializers.CharField()
    location = serializers.CharField()
    skills_details = SkillsDetailsSerializer()

    class Meta:
        model = Company
        exclude = ('user',)


class SearchProfileSerializer(serializers.ModelSerializer):

    skills = SkillSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = (
            'id', 'bio', 'city', 'country', 'country_name', 'location', 'skills'
        )


class SearchUserSerializer(serializers.ModelSerializer):
    objectID = serializers.IntegerField(source='id')
    profile = SearchProfileSerializer(required=False, read_only=True)
    profile_rank = serializers.FloatField(required=False, read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            'objectID', 'id', 'username', 'first_name', 'last_name', 'display_name', 'type',
            'profile', 'avatar_url', 'profile_rank'
        )


class SimplestUserSerializer(SimpleModelSerializer):
    company = serializers.SerializerMethodField(required=False, read_only=True)
    can_contribute = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'first_name', 'last_name', 'image', 'display_name', 'short_name', 'type',
            'is_developer', 'is_project_owner', 'is_project_manager', 'is_staff', 'is_admin', 'is_pay_admin',
            'verified', 'company', 'avatar_url', 'can_contribute', 'tax_location'
        )
        extra_kwargs = {
            'username': {'required': False}
        }

    def get_company(self, obj):
        try:
            if obj.company:
                return SimpleCompanySerializer(instance=obj.company).data
        except:
            if obj.profile:
                return dict(name=obj.profile.company)
        return

    def get_can_contribute(self, obj):
        return profile_check(obj)


class SimpleUserSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField(required=False, read_only=True)
    can_contribute = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name', 'short_name', 'type', 'image',
            'is_developer', 'is_project_owner', 'is_project_manager', 'is_staff', 'is_admin', 'is_pay_admin',
            'verified', 'company', 'avatar_url',
            'can_contribute', 'date_joined', 'agree_version', 'agreed_at', 'disagree_version', 'disagreed_at',
            'payoneer_signup_url', 'payoneer_status', 'exact_code', 'tax_location'
        )

    def get_company(self, obj):
        try:
            if obj.company:
                return SimpleCompanySerializer(instance=obj.company).data
        except:
            if obj.profile:
                return dict(name=obj.profile.company)
        return

    def get_can_contribute(self, obj):
        return profile_check(obj)


class SimpleProfileSerializer(serializers.ModelSerializer):
    city = serializers.CharField()
    skills = SkillSerializer(many=True)
    country = CountryField()
    country_name = serializers.CharField()
    location = serializers.CharField()
    btc_wallet = SimpleBTCWalletSerializer()
    skills_details = SkillsDetailsSerializer()

    class Meta:
        model = UserProfile
        exclude = ('user',)


class SimpleSkillsProfileSerializer(serializers.ModelSerializer):
    city = serializers.CharField()
    skills = SkillSerializer(many=True)
    country = CountryField()
    country_name = serializers.CharField()
    skills_details = SkillsDetailsSerializer()

    class Meta:
        model = UserProfile
        fields = ('id', 'skills', 'country', 'country_name', 'city', 'bio', 'skills_details')


class SimpleUserSkillsProfileSerializer(SimpleUserSerializer):
    profile = SimpleSkillsProfileSerializer(read_only=True, required=False)

    class Meta(SimpleUserSerializer.Meta):
        model = get_user_model()
        fields = (
            'id', 'username', 'first_name', 'last_name',
            'display_name', 'short_name', 'type',
            'image', 'avatar_url', 'profile'
        )


class InvoiceUserSerializer(serializers.ModelSerializer):
    profile = SimpleProfileSerializer(read_only=True, required=False, source='userprofile')

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name', 'type',
            'is_developer', 'is_project_owner', 'is_staff', 'is_admin', 'is_pay_admin',
            'verified', 'profile'
        )


class SimpleAbstractExperienceSerializer(serializers.ModelSerializer):
    start_month_display = serializers.CharField(read_only=True, required=False, source='get_start_month_display')
    end_month_display = serializers.CharField(read_only=True, required=False, source='get_end_month_display')

    class Meta:
        model = AbstractExperience
        exclude = ('user', 'created_at')


class AbstractExperienceSerializer(SimpleAbstractExperienceSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = AbstractExperience
        exclude = ('created_at',)


class SimpleWorkSerializer(SimpleAbstractExperienceSerializer):

    class Meta(SimpleAbstractExperienceSerializer.Meta):
        model = Work


class SimpleEducationSerializer(SimpleAbstractExperienceSerializer):

    class Meta(SimpleAbstractExperienceSerializer.Meta):
        model = Education


class SimpleProfileProjectSerializer(SimpleAbstractExperienceSerializer):

    class Meta(SimpleAbstractExperienceSerializer.Meta):
        model = ProfileProject


class SimpleConnectionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Connection
        fields = '__all__'


class SimpleUploadSerializer(serializers.ModelSerializer):
    url = serializers.CharField(required=False, read_only=True, source='file.url')
    name = serializers.SerializerMethodField(required=False, read_only=True)
    size = serializers.IntegerField(required=False, read_only=True, source='file.size')
    display_size = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = GenericUpload
        fields = ('id', 'url', 'name', 'created_at', 'size', 'display_size')

    def get_name(self, obj):
        return obj.file.name.split('/')[-1]

    def get_display_size(self, obj):
        filesize = obj.file.size
        converter = {'KB': 10**3, 'MB': 10**6, 'GB': 10**9, 'TB': 10**12}
        units = ['TB', 'GB', 'MB', 'KB']

        for label in units:
            conversion = converter[label]
            if conversion and filesize > conversion:
                return '%s %s' % (round(filesize/conversion, 2), label)
        return '%s %s' % (filesize, 'bytes')


class UploadSerializer(SimpleUploadSerializer):
    user = SimpleUserSerializer(
        required=False, read_only=True, default=CreateOnlyCurrentUserDefault()
    )

    class Meta(SimpleUploadSerializer.Meta):
        model = Upload
        fields = SimpleUploadSerializer.Meta.fields + ('user',)


class ContactRequestSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContactRequest
        fields = ('fullname', 'email', 'item', 'body')


class SimpleRatingSerializer(ContentTypeAnnotatedModelSerializer):
    created_by = SimpleUserSerializer(
        required=False, read_only=True, default=CreateOnlyCurrentUserDefault()
    )
    display_criteria = serializers.CharField(required=False, read_only=True, source='get_criteria_display')

    class Meta:
        model = Rating
        exclude = ('content_type', 'object_id', 'created_at')


class TaskInvoiceSerializer(serializers.ModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    client = InvoiceUserSerializer(required=False, read_only=True)
    developer = InvoiceUserSerializer(required=False, read_only=True)
    amount = serializers.JSONField(required=False, read_only=True)
    developer_amount = serializers.SerializerMethodField(required=False, read_only=True)
    tax_ratio = serializers.DecimalField(max_digits=19, decimal_places=4, required=False, read_only=True)
    exclude_payment_costs = serializers.BooleanField(required=False, read_only=True)

    class Meta:
        model = TaskInvoice
        fields = '__all__'

    def get_developer_amount(self, obj):
        current_user = self.get_current_user()
        if current_user and current_user.is_developer:
            try:
                participation = obj.task.participation_set.get(user=current_user)
                share = obj.task.get_user_participation_share(participation.id)
                return obj.get_amount_details(share=share)
            except:
                pass
        return obj.get_amount_details(share=0)


class InviteRequestSerializer(serializers.ModelSerializer):

    class Meta:
        model = InviteRequest
        fields = '__all__'
        extra_kwargs = {
            'cv': {'required': True}
        }
