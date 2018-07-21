from rest_framework import serializers

from tunga_comments.models import Comment
from tunga_utils.serializers import CreateOnlyCurrentUserDefault, UploadSerializer, SimpleUserSerializer


class CommentSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    uploads = UploadSerializer(read_only=True, required=False, many=True)
    text_body = serializers.CharField(required=False, read_only=True)
    html_body = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ('created_at',)
