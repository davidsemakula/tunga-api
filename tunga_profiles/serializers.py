from django_countries.serializer_fields import CountryField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga_profiles import sso_helper
from tunga_profiles.models import UserProfile, Education, Work, Connection, \
    DeveloperApplication, DeveloperInvitation, \
    Skill, Company, WhitePaperUser
from tunga_profiles.notifications import send_developer_invited_email
from tunga_profiles.signals import user_profile_updated
from tunga_utils.constants import SKILL_TYPE_OTHER
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.serializers import CreateOnlyCurrentUserDefault, \
    AbstractExperienceSerializer, \
    SkillsDetailsSerializer, SimplestUserSerializer, \
    SimpleSkillSerializer, NestedModelSerializer, \
    ContentTypeAnnotatedModelSerializer
from tunga_utils.validators import is_business_email


class ProfileSerializer(NestedModelSerializer,
                        ContentTypeAnnotatedModelSerializer):
    user = SimplestUserSerializer(required=False)
    city = serializers.CharField(required=False, allow_blank=True,
                                 allow_null=True)
    skills = SimpleSkillSerializer(required=False, many=True)
    skills_details = SkillsDetailsSerializer(required=False, read_only=True)
    country = CountryField(required=False)
    country_name = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = UserProfile
        fields = '__all__'

    def nested_save_override(self, validated_data, instance=None):
        initial_bio = None
        initial_location = None
        initial_skills = None

        if instance:
            initial_bio = instance.bio
            initial_location = instance.location
            initial_skills = [skill.name for skill in instance.skills.all()]
            list.sort(initial_skills)

        instance = super(ProfileSerializer, self).nested_save_override(
            validated_data, instance=instance)

        final_skills = [skill.name for skill in instance.skills.all()]
        list.sort(final_skills)
        if not instance or initial_bio != instance.bio or initial_location != instance.location or initial_skills != final_skills:
            user_profile_updated.send(sender=UserProfile, profile=instance)
        return instance

    def save_nested_user(self, data, instance, created=False):
        user = instance.user
        if user:
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            image = data.get('image', None)
            if image:
                user.image = image
            user.save()

    def save_nested_skills(self, data, instance, created=False):
        if data is not None:
            instance.skills = ', '.join(
                [skill.get('name', '') for skill in data])
            instance.save()

            for skill in data:
                try:
                    category = skill.get('type', None)
                    if category:
                        Skill.objects.filter(name=skill.get('name', ''),
                                             type=SKILL_TYPE_OTHER).update(
                            type=category)
                except:
                    pass

    def save_nested_city(self, data, instance, created=False):
        if data:
            instance.city = data
            instance.save()


class CompanySerializer(NestedModelSerializer,
                        ContentTypeAnnotatedModelSerializer):
    user = SimplestUserSerializer(required=False, read_only=False)
    city = serializers.CharField(required=False, allow_blank=True,
                                 allow_null=True)
    skills = SimpleSkillSerializer(required=False, many=True)
    country = CountryField(required=False)
    country_name = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = Company
        fields = '__all__'

    def save_nested_user(self, data, instance, created=False):
        user = instance.user
        if user:
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            image = data.get('image', None)
            if image:
                user.image = image
            user.save()

    def save_nested_skills(self, data, instance, created=False):
        if data is not None:
            instance.skills = ', '.join(
                [skill.get('name', '') for skill in data])
            instance.save()

    def save_nested_city(self, data, instance, created=False):
        if data:
            instance.city = data
            instance.save()


class EducationSerializer(AbstractExperienceSerializer):
    class Meta(AbstractExperienceSerializer.Meta):
        model = Education


class WorkSerializer(AbstractExperienceSerializer):
    class Meta(AbstractExperienceSerializer.Meta):
        model = Work


class ConnectionSerializer(NestedModelSerializer,
                           ContentTypeAnnotatedModelSerializer):
    from_user = SimplestUserSerializer(required=False, read_only=True,
                                       default=CreateOnlyCurrentUserDefault())
    to_user = SimplestUserSerializer(required=False, read_only=False)

    class Meta:
        model = Connection
        fields = '__all__'


class DeveloperApplicationSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = DeveloperApplication
        exclude = (
            'confirmation_key', 'confirmation_sent_at', 'used', 'used_at')


class DeveloperInvitationSerializer(serializers.ModelSerializer,
                                    GetCurrentUserAnnotatedSerializerMixin):
    created_by = serializers.PrimaryKeyRelatedField(required=False,
                                                    read_only=True,
                                                    default=CreateOnlyCurrentUserDefault())
    display_name = serializers.CharField(required=False, read_only=True)
    display_type = serializers.CharField(required=False, read_only=True)

    # resend = serializers.BooleanField(required=False, write_only=True, default=False)

    class Meta:
        model = DeveloperInvitation
        exclude = ('invitation_key', 'used', 'used_at')

    def is_valid(self, raise_exception=False):
        resend = self.initial_data.get('resend', False)
        email = self.initial_data.get('email', False)
        is_valid = super(DeveloperInvitationSerializer, self).is_valid(
            raise_exception=raise_exception and not resend)
        if resend and email:
            try:
                user_exists_on_sso = sso_helper.check_if_users_exists_in_sso(
                    current_user=self.get_current_user(),
                    email=email)
                invite = DeveloperInvitation.objects.get(email=email)
                self.instance = invite
                if invite and not user_exists_on_sso:
                    self._errors = {}

                    invite.first_name = self.initial_data.get('first_name',
                                                              invite.first_name)
                    invite.last_name = self.initial_data.get('last_name',
                                                             invite.last_name)
                    invite.type = self.initial_data.get('type', invite.type)
                    invite.save()

                    send_developer_invited_email.delay(invite.id, resend=True)
                    return True
            except:
                pass
        if self._errors and raise_exception:
            raise ValidationError(self.errors)
        return is_valid

    def create(self, validated_data):
        email = validated_data.get('email')
        user_role = validated_data.get('type')
        user_exists = sso_helper.check_if_users_exists_in_sso(
            current_user=self.get_current_user(),
            email=email)
        if user_exists:
            update_user_role = sso_helper.change_user_access_in_sso(
                current_user=self.get_current_user(),
                email=email,
                platform_role=user_role

            )
            if update_user_role:
                user_invite = super(DeveloperInvitationSerializer, self).create(
                    validated_data)
                send_developer_invited_email.delay(user_invite.id,
                                                   transfer_from_sso=True)
                return user_invite
        resend = self.initial_data.get('resend', False)
        if resend and self.instance:
            return self.instance
        user_invite = super(DeveloperInvitationSerializer, self).create(
            validated_data)
        send_developer_invited_email.delay(user_invite.id)
        return user_invite


class WhitePaperVisitorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhitePaperUser
        fields = (
            'first_name', 'last_name', 'company', 'phone_number', 'country',
            'email', 'paper')

    def validate_emaill(self, email):
        if is_business_email(email):
            return email
        else:
            return serializers.ValidationError(
                detail='You need to specify a business email')
