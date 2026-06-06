from django.contrib import admin

from .models import ChatMessage, ChatSession


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "is_active", "started_at", "last_active")
    search_fields = ("user__username", "title")
    list_filter = ("is_active",)

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "short_content", "created_at")
    list_filter = ("role",)
    search_fields = ("content", "session__user__username")

    @admin.display(description="content")
    def short_content(self, obj):
        return (obj.content or "")[:80]
