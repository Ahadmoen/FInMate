from rest_framework import serializers

from users.serializers import NotificationPreferenceSerializer  # noqa: F401

from .models import Alert, AlertLog, Notification
from .presentation import notification_body, notification_title


class AlertLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertLog
        fields = [
            "id",
            "channel",
            "status",
            "error_message",
            "sent_at",
            "created_at",
        ]


class AlertSerializer(serializers.ModelSerializer):
    logs = AlertLogSerializer(many=True, read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id",
            "user",
            "ticker",
            "signal",
            "reason",
            "alert_window",
            "logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    """Light-weight feed row for the bell icon list.

    Includes a small `alert_summary` denormalised so the list view
    doesn't need to join AlertDetail per row — the detail endpoint
    serves that.
    """

    ticker = serializers.CharField(source="alert.ticker", read_only=True)
    signal = serializers.CharField(source="alert.signal", read_only=True)
    alert_window = serializers.CharField(source="alert.alert_window", read_only=True)
    reason = serializers.CharField(source="alert.reason", read_only=True)
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "category",
            "read_at",
            "created_at",
            "title",
            "body",
            # Denormalised from the underlying Alert
            "ticker",
            "signal",
            "alert_window",
            "reason",
        ]
        # Exclude SerializerMethodField names — they are read-only by default.
        read_only_fields = [
            "id",
            "type",
            "category",
            "read_at",
            "created_at",
            "ticker",
            "signal",
            "alert_window",
            "reason",
        ]

    def get_title(self, obj: Notification) -> str:
        return notification_title(obj, obj.alert)

    def get_body(self, obj: Notification) -> str:
        return notification_body(obj.alert, notif_type=obj.type)
