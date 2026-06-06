from django.contrib import admin

from .models import ScrapeRun


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "status", "rows_processed", "started_at", "finished_at")
    list_filter = ("source", "status")
    search_fields = ("notes",)
