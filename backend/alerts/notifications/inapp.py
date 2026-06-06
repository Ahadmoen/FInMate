"""In-app notification — writes a Notification row.

This is the "in-app" channel: just a row in the `notification` table. The
mobile/web frontend polls `GET /api/v1/notifications/?unread=true` on a
30-second timer (and on tab focus) to display the bell badge + feed.

Decoupling rationale: in-app stays the source-of-truth for what the user
saw, even when email/Slack fail. n8n used to do this via webhook; now
Django writes the row in the same Celery task so there's no round-trip
and no auth/secret to manage.
"""
from __future__ import annotations

import logging

from alerts.models import Alert, Notification

logger = logging.getLogger(__name__)


def create_in_app_notification(
    *,
    user,
    alert: Alert,
    notification_type: str,
    category: str = "stock",
) -> Notification | None:
    """Create one Notification row pointing at the given Alert.

    `notification_type` must be one of Notification.Type values:
      - TOP_PICK       (Workflow A — single best STRONG_BUY)
      - DIGEST         (Workflow A — table of the rest)
      - POSITION_ALERT (Workflow B — SELL/STRONG_SELL on a holding)

    Idempotency: if a Notification row already exists for this
    (user, alert) pair we skip (some Celery setups retry tasks; this
    keeps the user from seeing duplicates).
    """
    try:
        notif, created = Notification.objects.get_or_create(
            user=user,
            alert=alert,
            defaults={"type": notification_type, "category": category},
        )
        if not created:
            logger.debug(
                "Notification already exists for user=%s alert=%s — skipping",
                user.id,
                alert.id,
            )
        return notif
    except Exception:
        logger.exception(
            "Failed to create Notification for user=%s alert=%s", user.id, alert.id
        )
        return None
