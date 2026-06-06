from django.urls import path

from .views import (
    AlertHistoryDetailView,
    AlertHistoryListView,
    NotificationDetailView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationPreferenceView,
    NotificationUnreadCountView,
)


urlpatterns = [
    # Alert history (the user's full audit trail)
    path("history/", AlertHistoryListView.as_view(), name="alerts-history"),
    path(
        "history/<int:id>/",
        AlertHistoryDetailView.as_view(),
        name="alerts-history-detail",
    ),

    # Notification preferences (which channels + windows)
    path(
        "preferences/",
        NotificationPreferenceView.as_view(),
        name="alerts-preferences",
    ),

    # In-app notification feed (bell icon)
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notifications-list",
    ),
    path(
        "notifications/unread-count/",
        NotificationUnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        "notifications/mark-all-read/",
        NotificationMarkAllReadView.as_view(),
        name="notifications-mark-all-read",
    ),
    path(
        "notifications/<uuid:id>/read/",
        NotificationMarkReadView.as_view(),
        name="notifications-mark-read",
    ),
    path(
        "notifications/<uuid:id>/detail/",
        NotificationDetailView.as_view(),
        name="notifications-detail",
    ),
]
