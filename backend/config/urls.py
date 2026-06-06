"""
Top-level URL configuration for the FinMate backend.

All API routes live under `/api/v1/`. JWT auth is at `/api/v1/login/`.
"""

from django.contrib import admin
from django.urls import include, path

from users.views import EmailLoginView


urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/v1/login/", EmailLoginView.as_view(), name="token_obtain_pair"),

    path("api/v1/users/", include("users.urls")),
    path("api/v1/portfolio/", include("portfolio.urls")),
    path("api/v1/alerts/", include("alerts.urls")),
    path("api/v1/core/", include("core.urls")),
    path("api/v1/chatbot/", include("chatbot.urls")),
    path("api/v1/chat/", include("chatbot.chat_urls")),
    path("api/v1/integrations/", include("integrations.urls")),
    path("api/v1/dashboard/", include("dashboard.urls")),
    path("api/v1/insights/", include("insights.urls")),
    path("api/v1/news/", include("news.urls")),
]
