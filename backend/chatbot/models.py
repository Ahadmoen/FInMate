from django.conf import settings
from django.db import models

from core.models import TimestampMixin


class ChatSession(TimestampMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "chat_session"
        ordering = ["-last_active"]

    def __str__(self) -> str:
        return f"ChatSession<{self.user.username} #{self.id}>"


class ChatMessage(TimestampMixin):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ASSISTANT = "ASSISTANT", "Assistant"

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    insight_card = models.JSONField(null=True, blank=True, default=None)
    sources_used = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "chat_message"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:60]}"
