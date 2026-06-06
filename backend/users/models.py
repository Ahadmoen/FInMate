import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimestampMixin


class CustomUser(AbstractUser):
    """Application user with notification-channel contact info."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    slack_webhook = models.URLField(blank=True)

    class Meta:
        db_table = "user"

    def __str__(self) -> str:
        return self.username


class UserKycProfile(models.Model):
    """KYC and permanent-address information for a user."""

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="kyc_profile",
    )
    cnic = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, choices=Gender.choices)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)

    class Meta:
        db_table = "user_kyc_profile"

    def __str__(self) -> str:
        return f"UserKycProfile<{self.user.username}>"


class InvestmentProfile(models.Model):
    """Investor suitability profile captured during registration."""

    class ExperienceLevel(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        EXPERT = "expert", "Expert"

    class RiskTolerance(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class IncomeRange(models.TextChoices):
        UNDER_50K = "under_50k", "Under 50,000"
        RANGE_50K_100K = "50k_100k", "50,000 - 100,000"
        RANGE_100K_250K = "100k_250k", "100,000 - 250,000"
        RANGE_250K_500K = "250k_500k", "250,000 - 500,000"
        RANGE_500K_1M = "500k_1m", "500,000 - 1,000,000"
        OVER_1M = "over_1m", "Over 1,000,000"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="investment_profile",
    )
    investment_experience = models.CharField(
        max_length=20,
        choices=ExperienceLevel.choices,
    )
    risk_tolerance = models.CharField(
        max_length=20,
        choices=RiskTolerance.choices,
    )
    investment_goals = models.JSONField(default=list)
    income_range = models.CharField(max_length=30, choices=IncomeRange.choices)

    class Meta:
        db_table = "investment_profile"

    def __str__(self) -> str:
        return f"InvestmentProfile<{self.user.username}>"


class NotificationPreference(models.Model):
    """Per-user notification preference settings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )

    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=False)
    slack_enabled = models.BooleanField(default=False)
    in_app_enabled = models.BooleanField(default=True)

    pre_market = models.BooleanField(default=True)
    mid_session = models.BooleanField(default=True)
    post_market = models.BooleanField(default=True)

    class Meta:
        db_table = "notification_preference"

    def __str__(self) -> str:
        return f"NotificationPreference<{self.user.username}>"


class DeviceToken(TimestampMixin):
    """Expo push token registered by a user's device at login."""

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    token = models.TextField()
    platform = models.CharField(max_length=10, choices=Platform.choices, blank=True)

    class Meta:
        db_table = "device_token"
        unique_together = ("user", "token")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"DeviceToken<{self.user_id} {self.platform}>"
