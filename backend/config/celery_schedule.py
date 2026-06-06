"""
Celery beat schedule for FinMate.

All times are in Asia/Karachi (PKT). Trading-day tasks run on weekdays only
(Monday–Friday) using crontab `day_of_week='mon-fri'`.
"""

from celery.schedules import crontab


WEEKDAYS = "mon-fri"


CELERY_BEAT_SCHEDULE = {
    # --------------------------------------------------------------------- #
    # Data ingestion (integrations.tasks)
    # --------------------------------------------------------------------- #
    "morning_full_fetch": {
        "task": "integrations.tasks.morning_full_fetch",
        "schedule": crontab(hour=6, minute=0, day_of_week=WEEKDAYS),
    },
    "hourly_refresh": {
        "task": "integrations.tasks.hourly_refresh",
        "schedule": crontab(minute=0, hour="9-15", day_of_week=WEEKDAYS),
    },
    # --------------------------------------------------------------------- #
    # Alert dispatch (alerts.tasks)
    # --------------------------------------------------------------------- #
    # Matches n8n Workflow A/B schedule: 09:00 / 12:00 / 18:40 PKT.
    # Each task fires the top pick immediately, schedules the digest
    # for +2 min and position alerts for +5 min via Celery countdown.
    "send_morning_alerts": {
        "task": "alerts.tasks.send_morning_alerts",
        "schedule": crontab(hour=9, minute=0, day_of_week=WEEKDAYS),
    },
    "send_midday_alerts": {
        "task": "alerts.tasks.send_midday_alerts",
        "schedule": crontab(hour=12, minute=0, day_of_week=WEEKDAYS),
    },
    "send_evening_digest": {
        "task": "alerts.tasks.send_evening_digest",
        "schedule": crontab(hour=18, minute=40, day_of_week=WEEKDAYS),
    },

    # --------------------------------------------------------------------- #
    # Registry refresh (integrations.tasks)
    # --------------------------------------------------------------------- #
    "registry_scraper": {
        "task": "integrations.tasks.run_registry_scraper",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
    },

    # --------------------------------------------------------------------- #
    # Maintenance (core.tasks)
    # --------------------------------------------------------------------- #
    "cleanup_old_alerts": {
        "task": "core.tasks.cleanup_old_alerts",
        "schedule": crontab(hour=2, minute=0),
    },
}
