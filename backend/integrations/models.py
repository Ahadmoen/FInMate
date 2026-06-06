from django.db import models

from core.models import TimestampMixin


class ScrapeRun(TimestampMixin):
    """Audit row for each scraper invocation. Useful for monitoring."""

    class Source(models.TextChoices):
        HISTORICAL = "HISTORICAL", "Historical"
        LIVE = "LIVE", "Live"
        NEWS = "NEWS", "News"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"

    source = models.CharField(max_length=15, choices=Source.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    rows_processed = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "scrape_run"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"ScrapeRun<{self.source} {self.status}>"
