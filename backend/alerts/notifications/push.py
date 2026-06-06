"""Push notification delivery via Expo Push API.

Sends to all registered device tokens for a user. Returns a result
dict compatible with services._log_send():
  {"status": "SENT"}
  {"status": "FAILED", "error": "..."}
  {"status": "SKIPPED", "reason": "..."}
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push_notification(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
) -> dict:
    if not tokens:
        return {"status": "SKIPPED", "reason": "no device tokens"}

    messages = [
        {
            "to": token,
            "title": title,
            "body": body,
            "sound": "default",
            "priority": "high",
            "data": data or {},
        }
        for token in tokens
    ]

    try:
        resp = requests.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        tickets = resp.json().get("data", [])

        for ticket in tickets:
            if ticket.get("status") == "error":
                logger.warning("Expo push ticket error: %s", ticket)

        if any(t.get("status") == "ok" for t in tickets):
            return {"status": "SENT"}
        return {"status": "FAILED", "error": "all tickets failed"}

    except Exception as exc:
        logger.error("Expo push request failed: %s", exc, exc_info=True)
        return {"status": "FAILED", "error": str(exc)}
