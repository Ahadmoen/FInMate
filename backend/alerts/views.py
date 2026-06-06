from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import NotificationPreference
from users.serializers import NotificationPreferenceSerializer

from .models import Alert, AlertDetail, Notification
from .presentation import notification_body, notification_title, window_label
from .serializers import AlertSerializer, NotificationSerializer

DEFAULT_FEED_DAYS = 10


class AlertHistoryListView(generics.ListAPIView):
    """GET /api/alerts/history/ — paginated list (20/page) of the user's alerts."""

    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).order_by("-created_at")


class AlertHistoryDetailView(generics.RetrieveAPIView):
    """GET /api/alerts/history/<id>/ — single alert detail (with delivery logs)."""

    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user)


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """
    GET / PUT /api/alerts/preferences/ — same NotificationPreference object as
    `/api/users/notifications/`, exposed under the alerts namespace too.
    """

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch"]

    def get_object(self):
        prefs, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return prefs


# -------------------------------------------------- in-app notification feed
class NotificationListView(generics.ListAPIView):
    """GET /api/alerts/notifications/?days=10&unread=true — the bell-icon feed.

    Each row is a thin denormalised pointer at an underlying Alert.
    Frontend pulls the rich payload on-demand via
    /api/alerts/notifications/<id>/detail/ when the user taps the row.
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        days_raw = self.request.query_params.get("days", str(DEFAULT_FEED_DAYS))
        try:
            days = max(1, min(int(days_raw), 90))
        except (TypeError, ValueError):
            days = DEFAULT_FEED_DAYS

        cutoff = timezone.now() - timedelta(days=days)
        qs = (
            Notification.objects
            .filter(user=self.request.user, created_at__gte=cutoff)
            .select_related("alert")
            .prefetch_related("alert__details")
            .order_by("-created_at")
        )
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(read_at__isnull=True)
        return qs


class NotificationUnreadCountView(APIView):
    """GET /api/alerts/notifications/unread-count/ — { count: N }.
    The bell badge polls this every 30s + on tab focus."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        n = Notification.objects.filter(
            user=request.user, read_at__isnull=True
        ).count()
        return Response({"count": n})


class NotificationMarkReadView(APIView):
    """PATCH /api/alerts/notifications/<id>/read/ — flip read_at = now()."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        notif = get_object_or_404(
            Notification, id=id, user=request.user
        )
        if notif.read_at is None:
            notif.read_at = timezone.now()
            notif.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(notif).data)


class NotificationMarkAllReadView(APIView):
    """POST /api/alerts/notifications/mark-all-read/ — clear the badge."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user, read_at__isnull=True
        ).update(read_at=timezone.now())
        return Response({"marked": updated})


class NotificationDetailView(APIView):
    """GET /api/alerts/notifications/<id>/detail/ — returns the rich
    AlertDetail.payload so the frontend can render the full card."""

    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        notif = get_object_or_404(
            Notification.objects.select_related("alert"),
            id=id, user=request.user,
        )
        detail = (
            AlertDetail.objects.filter(alert=notif.alert)
            .order_by("-created_at")
            .first()
        )
        alert = notif.alert
        return Response({
            "id": str(notif.id),
            "type": notif.type,
            "category": notif.category,
            "read_at": notif.read_at,
            "created_at": notif.created_at,
            "title": notification_title(notif, alert),
            "body": notification_body(alert, notif_type=notif.type, max_words=None),
            "window_label": window_label(alert.alert_window),
            "alert": {
                "id": str(alert.id),
                "ticker": alert.ticker,
                "symbols": alert.symbols,
                "signal": alert.signal,
                "alert_window": alert.alert_window,
                "reason": alert.reason,
                "created_at": alert.created_at,
            },
            "payload": detail.payload if detail else None,
        })
