"""Celery tasks that dispatch alerts at each PSX time window.

Fires from `config/celery_schedule.py` — the cron there is in PKT, so
these tasks run at 09:00 / 12:00 / 17:30 PKT Mon–Fri. Each task runs
Workflow A (top pick + delayed digest) AND Workflow B (delayed
portfolio alerts on holdings). The digest goes out 2 minutes after
the top pick to match the n8n cadence; position alerts go out 5
minutes after the top so users see the market view first.
"""
from __future__ import annotations

import logging

from celery import shared_task

from alerts import services

logger = logging.getLogger(__name__)


def _dispatch_window(window: str) -> dict:
    """Fire Workflow A (top + digest delayed) and Workflow B (delayed)."""
    top_result = services.dispatch_top_pick(window)
    # Digest goes 2 min after the top pick (n8n: 'Digest: wait 2 min')
    send_digest.apply_async(args=[window], countdown=120)
    # Portfolio alerts go 5 min after the top pick (n8n: 'Wait 5 min')
    send_position_alerts.apply_async(args=[window], countdown=300)
    return top_result


@shared_task
def send_morning_alerts() -> dict:
    """09:00 PKT — pre-market window."""
    return _dispatch_window("PRE_MARKET")


@shared_task
def send_midday_alerts() -> dict:
    """12:00 PKT — mid-session window."""
    return _dispatch_window("MID_SESSION")


@shared_task
def send_evening_digest() -> dict:
    """17:30 PKT — post-market window. (Cron name kept for compat.)"""
    return _dispatch_window("POST_MARKET")


@shared_task
def send_digest(window: str) -> dict:
    """Workflow A · Digest (table of the rest). Called 2 min after top."""
    try:
        return services.dispatch_digest(window)
    except Exception:
        logger.exception("send_digest(%s) failed", window)
        return {"sent": 0, "error": True}


@shared_task
def send_position_alerts(window: str) -> dict:
    """Workflow B · Portfolio holdings × SELL/STRONG_SELL signals."""
    try:
        return services.dispatch_position_alerts(window)
    except Exception:
        logger.exception("send_position_alerts(%s) failed", window)
        return {"sent": 0, "error": True}
