from django.urls import path

from .views import ChatSessionDetailView, ChatSessionListView, ChatView


urlpatterns = [
    path("ask/", ChatView.as_view(), name="chatbot-ask"),
    path("sessions/", ChatSessionListView.as_view(), name="chatbot-sessions"),
    path("sessions/<uuid:id>/", ChatSessionDetailView.as_view(), name="chatbot-session-detail"),
]
