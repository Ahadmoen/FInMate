"""Display helpers for in-app notification feed rows."""
from __future__ import annotations

from .models import Alert, Notification

WINDOW_LABELS = {
    "PRE_MARKET": "Pre-Market",
    "MID_SESSION": "Mid-Session",
    "POST_MARKET": "Post-Market",
}

TYPE_LABELS = {
    Notification.Type.TOP_PICK: "Top Pick",
    Notification.Type.DIGEST: "Market Digest",
    Notification.Type.POSITION_ALERT: "Position Alert",
    # DB stores plain strings — keep string keys for lookups too.
    "TOP_PICK": "Top Pick",
    "DIGEST": "Market Digest",
    "POSITION_ALERT": "Position Alert",
}

FEED_BODY_MAX_WORDS = 120


def truncate_words(text: str, max_words: int = FEED_BODY_MAX_WORDS) -> str:
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip() + "…"


def window_label(alert_window: str) -> str:
    return WINDOW_LABELS.get(alert_window, alert_window.replace("_", " ").title())


def notification_title(notif: Notification, alert: Alert) -> str:
    window = window_label(alert.alert_window)
    if notif.type == Notification.Type.DIGEST:
        return f"{TYPE_LABELS[notif.type]} — {window}"
    ticker = alert.ticker if alert.ticker != "DIGEST" else "PSX"
    return f"{TYPE_LABELS.get(notif.type, notif.type)}: {ticker} — {window}"


def _summary_from_payload(payload: dict, *, notif_type: str) -> str:
    if not payload:
        return ""
    summary = (payload.get("summary") or "").strip()
    if summary:
        return summary
    if notif_type == Notification.Type.DIGEST:
        count = payload.get("count") or len(payload.get("tickers") or [])
        return f"Digest of {count} strong-buy moves."
    return ""


def notification_body(
    alert: Alert,
    *,
    notif_type: str = "",
    max_words: int | None = FEED_BODY_MAX_WORDS,
) -> str:
    text = (alert.reason or "").strip()
    if not text:
        detail = alert.details.order_by("-created_at").first()
        if detail:
            text = _summary_from_payload(detail.payload or {}, notif_type=notif_type)
    if max_words is None:
        return text
    return truncate_words(text, max_words)
