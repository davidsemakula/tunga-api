# -*- coding: utf-8 -*-

import datetime

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import SetPasswordForm
from django.core.validators import EmailValidator
from django.db.models.aggregates import Avg
from django.db.models.query_utils import Q
from django.utils import six
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from rest_auth.registration.serializers import RegisterSerializer
from rest_auth.serializers import TokenSerializer, PasswordResetSerializer, \
    PasswordResetConfirmSerializer, PasswordChangeSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga import settings
from tunga_auth.forms import TungaPasswordResetForm
from tunga_auth.models import USER_TYPE_CHOICES, EmailVisitor, TungaUser
from tunga_profiles import sso_helper
from tunga_profiles.notifications import \
    send_developer_invitation_accepted_email
from tunga_utils.constants import USER_TYPE_DEVELOPER, STATUS_REJECTED, \
    STATUS_INITIAL, STATUS_ACCEPTED, USER_SOURCE_MANUAL, USER_CATEGORY_DEVELOPER
from tunga_profiles.models import Connection, DeveloperApplication, UserProfile, \
    DeveloperInvitation, Company
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.models import Rating
from tunga_utils.serializers import SimpleProfileSerializer, \
    SimpleUserSerializer, SimpleWorkSerializer, \
    SimpleEducationSerializer, SimpleConnectionSerializer, \
    SimpleCompanySerializer, SimplestCompanySerializer, \
    NestedModelSerializer, SimpleProfileProjectSerializer
from tunga_utils.validators import validate_email, validate_username


class UserSerializer(NestedModelSerializer, SimpleUserSerializer,
                     GetCurrentUserAnnotatedSerializerMixin):
    display_name = serializers.CharField(read_only=True, required=False)
    display_type = serializers.CharField(read_only=True, required=False)
    display_category = serializers.CharField(read_only=True, required=False)
    is_developer = serializers.BooleanField(read_only=True, required=False)
    is_designer = serializers.BooleanField(read_only=True, required=False)
    is_project_owner = serializers.BooleanField(read_only=True, required=False)
    is_project_manager = serializers.BooleanField(read_only=True,
                                                  required=False)
    is_admin = serializers.BooleanField(read_only=True, required=False)
    profile = SimpleProfileSerializer(read_only=True, required=False)
    company = SimplestCompanySerializer(required=False)
    work = SimpleWorkSerializer(many=True, source='work_set', read_only=True,
                                required=False)
    education = SimpleEducationSerializer(many=True, source='education_set',
                                          read_only=True, required=False)

    project = SimpleProfileProjectSerializer(many=True,
                                             source='profileproject_set',
                                             read_only=True, required=False)
    can_connect = serializers.SerializerMethodField(read_only=True,
                                                    required=False)
    request = serializers.SerializerMethodField(read_only=True, required=False)
    connection = serializers.SerializerMethodField(read_only=True,
                                                   required=False)
    tasks_created = serializers.SerializerMethodField(read_only=True,
                                                      required=False)
    tasks_completed = serializers.SerializerMethodField(read_only=True,
                                                        required=False)
    satisfaction = serializers.SerializerMethodField(read_only=True,
                                                     required=False)
    ratings = serializers.SerializerMethodField(read_only=True, required=False)
    avatar_url = serializers.URLField(read_only=True, required=False)
    exact_code = serializers.CharField(read_only=True, required=False)
    tax_location = serializers.CharField(read_only=True, required=False)
    is_pay_admin = serializers.BooleanField(read_only=True, required=False)

    class Meta:
        model = get_user_model()
        exclude = (
            'password', 'is_superuser', 'groups', 'user_permissions',
            'is_active')
        read_only_fields = (
            # 'username', 'email',
            'date_joined', 'last_login', 'is_staff', 'payoneer_signup_url',
            'payoneer_status'
        )

    def validate_username(self, attrs):
        if self.context and self.context.get('request', None):
            request = self.context.get('request', None)
            if request.method == 'POST':
                validate_username(attrs)
        return attrs

    def validate_email(self, attrs):
        if self.context and self.context.get('request', None):
            request = self.context.get('request', None)
            if request.method == 'POST':
                validate_email(attrs)
                pass
        return attrs

    def save_nested_company(self, data, instance, created=False):
        if data:
            company = instance.company
            if not company:
                company = Company(user=instance)

            for key, value in six.iteritems(data):
                setattr(company, key, value)
            company.save()

    def get_can_connect(self, obj):
        current_user = self.get_current_user()
        if current_user:
            if not current_user.is_developer and not obj.is_developer or current_user.pending:
                return False
            has_requested = obj.connections_initiated.filter(
                to_user=current_user).count()
            if has_requested:
                return False
            has_accepted_or_been_requested = obj.connection_requests.exclude(
                status=STATUS_REJECTED
            ).filter(from_user=current_user).count() > 0
            return not has_accepted_or_been_requested
        return False

    def get_request(self, obj):
        current_user = self.get_current_user()
        if current_user:
            try:
                connection = obj.connections_initiated.get(to_user=current_user,
                                                           status=STATUS_INITIAL)
                return connection.id
            except:
                pass
        return None

    def get_connection(self, obj):
        current_user = self.get_current_user()
        if current_user:
            try:
                connection = Connection.objects.filter(
                    (Q(to_user=current_user) & Q(from_user=obj)) | (
                            Q(to_user=obj) & Q(from_user=current_user))
                ).latest('created_at')
                return SimpleConnectionSerializer(connection).data
            except:
                pass
        return None

    def get_tasks_created(self, obj):
        return obj.tasks_created.count()

    def get_tasks_completed(self, obj):
        return obj.participation_set.filter(task__closed=True,
                                            status=STATUS_ACCEPTED).count()

    def get_satisfaction(self, obj):
        score = None
        if obj.type == USER_TYPE_DEVELOPER:
            score = obj.participation_set.filter(
                task__closed=True, status=STATUS_ACCEPTED
            ).aggregate(satisfaction=Avg('task__satisfaction'))['satisfaction']
            if score:
                score = '{:0,.0f}%'.format(score * 10)
        return score

    def get_ratings(self, obj):
        score = None
        if obj.type == USER_TYPE_DEVELOPER:
            query = Rating.objects.filter(
                tasks__closed=True, tasks__participants=obj,
                tasks__participation__status=STATUS_ACCEPTED
            ).order_by('criteria')
            details = query.values('criteria').annotate(avg=Avg('score'))
            criteria_choices = dict(
                Rating._meta.get_field('criteria').flatchoices)
            for rating in details:
                rating['display_criteria'] = criteria_choices[
                    rating['criteria']]
                rating['display_avg'] = rating['avg'] and '{:0,.0f}%'.format(
                    rating['avg'] * 10)
            avg = query.aggregate(avg=Avg('score'))['avg']
            score = {'avg': avg, 'display_avg': avg and '{:0,.0f}%'.format(
                avg * 10) or None, 'details': details}
        return score


class AccountInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            'username', 'email', 'first_name', 'last_name', 'type', 'image')

    def validate(self, attrs):
        super(AccountInfoSerializer, self).validate(attrs)

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user:
            raise serializers.ValidationError('Something went wrong')

        password = self.initial_data.get('password', None)
        if not password or not user.check_password(password):
            raise serializers.ValidationError({'password': 'Wrong password'})
        return attrs


class TungaRegisterSerializer(RegisterSerializer):
    type = serializers.ChoiceField(required=True, choices=USER_TYPE_CHOICES,
                                   allow_blank=False, allow_null=False)
    first_name = serializers.CharField(required=True, allow_blank=False,
                                       allow_null=False)
    last_name = serializers.CharField(required=True, allow_blank=False,
                                      allow_null=False)
    key = serializers.CharField(required=False, write_only=True,
                                allow_blank=True, allow_null=True)

    def save(self, request):
        email = self.initial_data.get('email', None)
        user_type = self.initial_data.get('type', None)
        confirm_key = self.initial_data.get('key', None)
        invite_key = self.initial_data.get('invite_key', None)
        application = None
        invitation = None
        user_category = USER_CATEGORY_DEVELOPER
        cleaned_data = self.get_cleaned_data()

        if confirm_key:
            try:
                application = DeveloperApplication.objects.get(
                    confirmation_key=confirm_key, used=False)
                user_type = USER_TYPE_DEVELOPER
            except:
                raise ValidationError({'key': 'Invalid or expired key'})
        elif invite_key:
            try:
                invitation = DeveloperInvitation.objects.get(
                    invitation_key=invite_key, used=False)
                user_type = invitation.type
                user_category = invitation.category
            except:
                raise ValidationError({'invite_key': 'Invalid or expired key'})

        if application or invitation:
            # Skip email activation for developer applications and invitations
            adapter = get_adapter()
            adapter.stash_verified_email(request, email)

        user = super(TungaRegisterSerializer, self).save(request)
        user.type = user_type
        if user.type == USER_TYPE_DEVELOPER:
            user.category = user_category
        user.first_name = self.initial_data['first_name']
        user.last_name = self.initial_data['last_name']
        user.pending = False
        user.save()

        sso_helper.sync_user_sso(user, password=cleaned_data.get('password1'))

        if application:
            application.used = True
            application.used_at = datetime.datetime.utcnow()
            application.save()

            profile = UserProfile(user=user,
                                  phone_number=application.phone_number,
                                  country=application.country)
            profile.city = application.city
            profile.save()

            # if invitation:
            #     invitation.used = True
            #     invitation.used_at = datetime.datetime.utcnow()
            #     invitation.save()

            # Notify admins that developer has accepted invitation

            send_developer_invitation_accepted_email.delay(invitation.id)
        return user


class TungaDefaultPasswordChangeSerializer(PasswordChangeSerializer):

    def save(self):
        old_password = self.validated_data['old_password']
        new_password = self.validated_data['new_password1']
        sso_password_change = sso_helper.change_sso_user_password(self.user,
                                                                  old_password=old_password,
                                                                  new_password=new_password)
        if sso_password_change:
            self.set_password_form.save()
        else:
            raise serializers.ValidationError('Password not saved')

        if not self.logout_on_password_change:
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(self.request, self.user)


class TungaTokenSerializer(TokenSerializer):
    user = UserSerializer(read_only=True, required=False)

    class Meta:
        model = TokenSerializer.Meta.model
        fields = ('key', 'user')


class TungaPasswordResetSerializer(PasswordResetSerializer):
    password_reset_form_class = TungaPasswordResetForm

    def get_email_options(self):
        return {
            "email_template_name": "tunga/email/password_reset.html",
            "html_email_template_name": "tunga/email/password_reset.html"
        }


class TungaPasswordResetConfirmSerializer(PasswordResetConfirmSerializer):

    def save(self):
        try:
            uid = force_text(
                urlsafe_base64_decode(self.initial_data.get('uid', None)))
            user = get_user_model().objects.get(pk=uid)
            email_address = EmailAddress.objects.add_email(
                None, user, user.email
            )
            email_address.verified = True
            email_address.primary = True
            email_address.save()
            new_password = self.validated_data['new_password1']
            if user.source == USER_SOURCE_MANUAL and user.password == "":
                sso_helper.set_sso_user_password(user=user,
                                                 new_password=new_password,
                                                 over_ride=True)
            else:
                if sso_helper.set_sso_user_password(user=user,
                                                    new_password=new_password):
                    pass
                else:
                    return ValidationError('Password not reset please try again')

            user.set_password(new_password)
            return user
        except:
            pass


class EmailVisitorSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, validators=[
        EmailValidator()])  # Disables uniqueness validator

    class Meta:
        model = EmailVisitor
        fields = '__all__'

    def create_visitor(self, email):
        visitor, created = EmailVisitor.objects.update_or_create(
            email=email, defaults=dict(last_login_at=datetime.datetime.utcnow())
        )
        return visitor

    def create(self, validated_data):
        return self.create_visitor(validated_data.get('email'))

    def update(self, instance, validated_data):
        return self.create_visitor(validated_data.get('email'))
