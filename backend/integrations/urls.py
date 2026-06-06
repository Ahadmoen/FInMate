from django.urls import path

from .views import IntegrationStatusView


urlpatterns = [
    path("status/", IntegrationStatusView.as_view(), name="integration-status"),
]
