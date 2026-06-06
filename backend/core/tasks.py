"""
Core maintenance tasks. Heavy data-ingestion tasks live in `integrations.tasks`
and alert dispatch lives in `alerts.tasks` — this module is for cross-cutting
housekeeping like alert/log cleanup.
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def cleanup_old_alerts():
    """Delete alert records older than 30 days to keep the table small."""
    from alerts.models import Alert, AlertLog

    cutoff = timezone.now() - timedelta(days=30)
    log_count, _ = AlertLog.objects.filter(created_at__lt=cutoff).delete()
    alert_count, _ = Alert.objects.filter(created_at__lt=cutoff).delete()
    return {"alerts_deleted": alert_count, "logs_deleted": log_count}
