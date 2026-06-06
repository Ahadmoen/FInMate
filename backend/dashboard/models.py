from django.db import models


class DashboardCache(models.Model):
    cache_key = models.CharField(max_length=255, unique=True)
    data = models.JSONField()
    cached_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "dashboard_cache"
