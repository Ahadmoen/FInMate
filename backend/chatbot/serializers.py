from rest_framework import serializers

from .models import ChatMessage, ChatSession


def _assistant_extras(message: ChatMessage) -> tuple[object | None, list]:
    """Normalize insight_card/citations from column + legacy sources_used shapes."""
    insight_card = message.insight_card
    citations: list = []

    sources = message.sources_used
    if isinstance(sources, dict):
        insight_card = insight_card or sources.get("insight_card")
        raw_citations = sources.get("citations")
        if isinstance(raw_citations, list):
            citations = raw_citations
    elif isinstance(sources, list):
        citations = sources

    return insight_card, citations


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "session", "role", "content", "insight_card", "sources_used", "created_at"]
        read_only_fields = ["id", "session", "created_at"]


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ["id", "title", "started_at", "last_active", "is_active"]


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = ["id", "title", "started_at", "last_active", "is_active", "messages"]


class RecentChatSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(source="id")
    title = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField(source="last_active")
    message_count = serializers.IntegerField()

    def get_title(self, obj):
        if obj.title:
            return obj.title
        content = getattr(obj, "first_user_message", None)
        if content:
            return content.strip()[:255]
        return ""


class SessionMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "created_at"]

    def to_representation(self, instance):
        data = {
            "id": str(instance.id),
            "role": instance.role.lower(),
            "content": instance.content,
            "created_at": serializers.DateTimeField().to_representation(
                instance.created_at
            ),
        }
        if instance.role == ChatMessage.Role.ASSISTANT:
            insight_card, citations = _assistant_extras(instance)
            data["insight_card"] = insight_card
            data["citations"] = citations
        return data


class ChatAskSerializer(serializers.Serializer):
    message = serializers.CharField()
    session_id = serializers.UUIDField(required=False, allow_null=True)