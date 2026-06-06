from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, DeviceToken, NotificationPreference


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("id", "username", "email", "phone_number", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    search_fields = ("username", "email", "phone_number", "whatsapp_number")

    fieldsets = UserAdmin.fieldsets + (
        ("FinMate contact info", {
            "fields": ("phone_number", "whatsapp_number", "slack_webhook"),
        }),
    )


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "platform", "created_at")
    list_filter = ("platform",)
    search_fields = ("user__username", "user__email", "token")
    readonly_fields = ("created_at", "updated_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "email_enabled",
        "whatsapp_enabled",
        "slack_enabled",
        "pre_market",
        "mid_session",
        "post_market",
    )
    list_filter = ("email_enabled", "whatsapp_enabled", "slack_enabled")
    search_fields = ("user__username", "user__email")
