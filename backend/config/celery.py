"""
Celery application for the FinMate project.

The beat schedule itself lives in `config/celery_schedule.py` and is loaded
automatically through Django settings (CELERY_BEAT_SCHEDULE).
"""

import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
