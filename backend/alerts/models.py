from django.conf import settings
from django.db import models

from core.models import TimestampMixin


class Alert(TimestampMixin):
    class Signal(models.TextChoices):
        BUY = "BUY", "Buy"
        HOLD = "HOLD", "Hold"
        SELL = "SELL", "Sell"

    class Window(models.TextChoices):
        PRE_MARKET = "PRE_MARKET", "Pre-market"
        MID_SESSION = "MID_SESSION", "Mid-session"
        POST_MARKET = "POST_MARKET", "Post-market"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    ticker = models.CharField(max_length=10)
    symbols = models.JSONField(
        default=list,
        help_text=(
            "All tickers this alert is about — single-element list for "
            "TOP_PICK/POSITION_ALERT, full list for DIGEST. Lets the "
            "frontend query notifications by stock symbol via Postgrest's "
            "jsonb-contains operator: ?symbols=cs.[\"HBL\"]"
        ),
    )
    signal = models.CharField(max_length=10, choices=Signal.choices)
    reason = models.TextField()
    alert_window = models.CharField(max_length=15, choices=Window.choices)

    class Meta:
        db_table = "alert"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} {self.ticker} {self.signal} [{self.alert_window}]"


class AlertLog(TimestampMixin):
    class Channel(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        EMAIL = "EMAIL", "Email"
        SLACK = "SLACK", "Slack"
        PUSH = "PUSH", "Push"

    class Status(models.TextChoices):
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        PENDING = "PENDING", "Pending"

    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "alert_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AlertLog<{self.alert_id} {self.channel} {self.status}>"


class AlertDetail(TimestampMixin):
    """Rich per-alert payload — what was actually rendered/sent.

    One row per Alert, written alongside it by the n8n notification
    workflows. The JSONB blob carries the ticker(s), price snapshot,
    LLM-generated plain-English summary, technicals, and news links —
    everything the frontend needs to render a detailed view when the
    user taps a notification in their feed.
    """

    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE,
        related_name="details",
    )
    payload = models.JSONField(
        default=dict,
        help_text=(
            "Full rendered context. Shape varies by notification type:\n"
            "  - TOP_PICK / POSITION_ALERT: {ticker, signal, close, change_pct, "
            "rsi14, ma50, ma200, news: [...], summary, window_label}\n"
            "  - DIGEST: {tickers: [list of summaries], count, window_label}"
        ),
    )

    class Meta:
        db_table = "alert_detail"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AlertDetail<{self.alert_id}>"


class Notification(TimestampMixin):
    """Per-user feed entry for the frontend.

    One row per notification event. Links to the underlying Alert and
    carries denormalised type + category fields so the app can render
    the feed without joining alert_detail (which it can pull on-demand
    when the user taps to see more).
    """

    class Type(models.TextChoices):
        TOP_PICK = "TOP_PICK", "Top Pick"
        DIGEST = "DIGEST", "Digest"
        POSITION_ALERT = "POSITION_ALERT", "Position Alert"

    class Category(models.TextChoices):
        STOCK = "stock", "Stock"
        DIGEST = "digest", "Digest"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    category = models.CharField(max_length=10, choices=Category.choices)
    read_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when the user opens the notification in the app.",
    )

    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Notification<{self.user_id} {self.type} {self.category}>"
