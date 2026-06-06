import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import AccessToken

from .models import InvestmentProfile, NotificationPreference, UserKycProfile


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    phone_number = serializers.CharField(required=True)
    cnic = serializers.CharField(required=True)
    date_of_birth = serializers.DateField(required=True)
    gender = serializers.ChoiceField(
        choices=UserKycProfile.Gender.choices,
        required=True,
    )
    city = serializers.CharField(required=True)
    province = serializers.CharField(required=True)
    postal_code = serializers.CharField(required=True)
    investment_experience = serializers.ChoiceField(
        choices=InvestmentProfile.ExperienceLevel.choices,
        required=True,
    )
    risk_tolerance = serializers.ChoiceField(
        choices=InvestmentProfile.RiskTolerance.choices,
        required=True,
    )
    investment_goals = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                "short_term",
                "long_term",
                "trading",
                "dividend_income",
            ]
        ),
        allow_empty=False,
        required=True,
    )
    income_range = serializers.ChoiceField(
        choices=InvestmentProfile.IncomeRange.choices,
        required=True,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "cnic",
            "date_of_birth",
            "gender",
            "city",
            "province",
            "postal_code",
            "investment_experience",
            "risk_tolerance",
            "investment_goals",
            "income_range",
        ]
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
            "email": {"required": True},
        }

    def create(self, validated_data):
        cnic = validated_data.pop("cnic")
        date_of_birth = validated_data.pop("date_of_birth")
        gender = validated_data.pop("gender")
        city = validated_data.pop("city")
        province = validated_data.pop("province")
        postal_code = validated_data.pop("postal_code")

        investment_experience = validated_data.pop("investment_experience")
        risk_tolerance = validated_data.pop("risk_tolerance")
        investment_goals = validated_data.pop("investment_goals")
        income_range = validated_data.pop("income_range")
        validated_data["username"] = self._generate_username(validated_data["email"])

        with transaction.atomic():
            user = User.objects.create_user(**validated_data)
            UserKycProfile.objects.create(
                user=user,
                cnic=cnic,
                date_of_birth=date_of_birth,
                gender=gender,
                city=city,
                province=province,
                postal_code=postal_code,
            )
            InvestmentProfile.objects.create(
                user=user,
                investment_experience=investment_experience,
                risk_tolerance=risk_tolerance,
                investment_goals=investment_goals,
                income_range=income_range,
            )
            NotificationPreference.objects.create(
                user=user,
                email_enabled=True,
                whatsapp_enabled=True,
                in_app_enabled=True,
            )
            return user

    def _generate_username(self, email: str) -> str:
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", email.split("@")[0]).strip("_").lower()
        if not base:
            base = "user"

        username = base
        suffix = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}_{suffix}"
            suffix += 1
        return username

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_date_of_birth(self, value):
        if value >= timezone.localdate():
            raise serializers.ValidationError("Date of birth must be in the past.")
        return value

    def validate_cnic(self, value):
        normalized = value.strip()
        if len(normalized) < 10:
            raise serializers.ValidationError("CNIC appears too short.")
        return normalized


class UserKycProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserKycProfile
        fields = [
            "cnic",
            "date_of_birth",
            "gender",
            "city",
            "province",
            "postal_code",
        ]


class InvestmentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentProfile
        fields = [
            "investment_experience",
            "risk_tolerance",
            "investment_goals",
            "income_range",
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "whatsapp_number",
            "slack_webhook",
        ]
        read_only_fields = ["id", "username", "email"]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "in_app_enabled",
            "email_enabled",
            "whatsapp_enabled",
            "slack_enabled",
            "in_app_enabled",
            "pre_market",
            "mid_session",
            "post_market",
        ]
        read_only_fields = ["id"]


class UserKycUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    whatsapp_number = serializers.CharField(required=False, allow_blank=True)
    slack_webhook = serializers.URLField(required=False, allow_blank=True)
    cnic = serializers.CharField(required=False)
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.ChoiceField(choices=UserKycProfile.Gender.choices, required=False)
    city = serializers.CharField(required=False)
    province = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "whatsapp_number",
            "slack_webhook",
            "cnic",
            "date_of_birth",
            "gender",
            "city",
            "province",
            "postal_code",
        ]

    def validate_date_of_birth(self, value):
        if value >= timezone.localdate():
            raise serializers.ValidationError("Date of birth must be in the past.")
        return value

    def update(self, instance, validated_data):
        kyc_fields = {"cnic", "date_of_birth", "gender", "city", "province", "postal_code"}
        kyc_data = {k: validated_data.pop(k) for k in kyc_fields if k in validated_data}

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(update_fields=list(validated_data.keys()) or None)

        if kyc_data:
            kyc = instance.kyc_profile
            for attr, value in kyc_data.items():
                setattr(kyc, attr, value)
            kyc.save(update_fields=list(kyc_data.keys()))

        return instance

    def to_representation(self, instance):
        return {
            "first_name": instance.first_name,
            "last_name": instance.last_name,
            "phone_number": instance.phone_number,
            "whatsapp_number": instance.whatsapp_number,
            "slack_webhook": instance.slack_webhook,
            "kyc_profile": UserKycProfileSerializer(instance.kyc_profile).data,
        }


class UserFullDetailsSerializer(serializers.ModelSerializer):
    kyc_profile = UserKycProfileSerializer(read_only=True)
    investment_profile = InvestmentProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "whatsapp_number",
            "slack_webhook",
            "kyc_profile",
            "investment_profile",
        ]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
    )


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD

    def validate(self, attrs):
        email = attrs.get(self.username_field, "").strip().lower()
        password = attrs.get("password")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed("No active account found with the given credentials") from exc

        if not user.is_active:
            raise AuthenticationFailed("Account is not active")

        if not user.check_password(password):
            raise AuthenticationFailed("Invalid credentials")

        access = AccessToken.for_user(user)
        return {"access": str(access)}
