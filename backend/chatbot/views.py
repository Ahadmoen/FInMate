from django.db.models import Count, OuterRef, Subquery
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ml_services import chatbot_rag

from .models import ChatMessage, ChatSession
from .serializers import (
    ChatAskSerializer,
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
    RecentChatSessionSerializer,
    SessionMessageSerializer,
)
from .session_helpers import get_user_session


def _parse_query_int(value, default, *, minimum=0):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


class ChatView(APIView):
    """
    POST /api/chatbot/ask/
    body: { "message": "Should I buy Apple?", "session_id": "<uuid>" (optional) }
    Saves the user message, calls the RAG service, saves the assistant reply.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChatAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]
        session_id = serializer.validated_data.get("session_id")

        session, is_new = self._get_or_create_session(request.user, session_id)

        if is_new and not session.title:
            session.title = message[:255]
            session.save(update_fields=["title"])

        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.USER,
            content=message,
        )

        answer = chatbot_rag.ask(
            question=message,
            user=request.user,
            session_id=session.id,
        )

        assistant_payload = {"content": answer}
        if isinstance(answer, dict):
            sources_used = {}
            if "citations" in answer:
                sources_used["citations"] = answer["citations"]
            assistant_payload = {
                "content": answer.get("content") or answer.get("answer") or "",
                "insight_card": answer.get("insight_card"),
                "sources_used": sources_used,
            }

        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.ASSISTANT,
            content=assistant_payload["content"],
            insight_card=assistant_payload.get("insight_card"),
            sources_used=assistant_payload.get("sources_used", {}),
        )

        session.save(update_fields=["last_active"])

        return Response(
            {"answer": assistant_payload["content"], "session_id": session.id},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_or_create_session(user, session_id):
        if session_id:
            session = ChatSession.objects.filter(
                id=session_id,
                user=user,
                is_active=True,
            ).first()
            if session:
                return session, False
        return ChatSession.objects.create(user=user), True


class ChatSessionListView(generics.ListAPIView):
    """GET /api/chatbot/sessions/ — user's chat sessions."""

    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user, is_active=True)


class ChatSessionDetailView(generics.RetrieveAPIView):
    """GET /api/chatbot/sessions/<id>/ — full message history for one session."""

    serializer_class = ChatSessionDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user, is_active=True)


class ChatSessionRecentListView(APIView):
    """GET /api/v1/chat/sessions/ — recent chat sessions for the drawer."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = _parse_query_int(request.query_params.get("limit"), 30, minimum=1)
        offset = _parse_query_int(request.query_params.get("offset"), 0)

        first_user_message = (
            ChatMessage.objects.filter(
                session=OuterRef("pk"),
                role=ChatMessage.Role.USER,
            )
            .order_by("created_at")
            .values("content")[:1]
        )

        sessions = (
            ChatSession.objects.filter(user=request.user, is_active=True)
            .annotate(
                message_count=Count("messages"),
                first_user_message=Subquery(first_user_message),
            )
            .order_by("-last_active")[offset : offset + limit]
        )

        serializer = RecentChatSessionSerializer(sessions, many=True)
        return Response({"sessions": serializer.data})


class ChatSessionMessagesView(APIView):
    """GET /api/v1/chat/sessions/<session_id>/messages/ — full thread."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = get_user_session(request.user, session_id)
        messages = session.messages.order_by("created_at")
        return Response(
            {
                "session_id": str(session.id),
                "messages": SessionMessageSerializer(messages, many=True).data,
            }
        )


class ChatSessionDeleteView(APIView):
    """DELETE /api/v1/chat/sessions/<session_id>/ — remove from recent chats."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, session_id):
        session = get_user_session(request.user, session_id)
        session.is_active = False
        session.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
