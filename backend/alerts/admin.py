from django.contrib import admin

from .models import Alert, AlertLog


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "ticker", "signal", "alert_window", "created_at")
    list_filter = ("signal", "alert_window")
    search_fields = ("user__username", "ticker", "reason")


@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display = ("id", "alert", "channel", "status", "sent_at", "created_at")
    list_filter = ("channel", "status")
    search_fields = ("alert__user__username", "alert__ticker", "error_message")
