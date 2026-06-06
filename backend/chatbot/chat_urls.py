from django.urls import path

from .views import (
    ChatSessionDeleteView,
    ChatSessionMessagesView,
    ChatSessionRecentListView,
)


urlpatterns = [
    path("sessions/", ChatSessionRecentListView.as_view(), name="chat-sessions"),
    path(
        "sessions/<uuid:session_id>/messages/",
        ChatSessionMessagesView.as_view(),
        name="chat-session-messages",
    ),
    path(
        "sessions/<uuid:session_id>/",
        ChatSessionDeleteView.as_view(),
        name="chat-session-delete",
    ),
]
