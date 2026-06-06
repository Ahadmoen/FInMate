from datetime import timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken


User = get_user_model()


class RegisterFlowTests(APITestCase):
    def setUp(self):
        self.url = reverse("user-register")
        self.payload = {
            "email": "haider@example.com",
            "password": "MyStrongPassword123!",
            "first_name": "Haider",
            "last_name": "Khan",
            "phone_number": "+923001112233",
            "cnic": "12345-1234567-1",
            "date_of_birth": "2000-01-01",
            "gender": "male",
            "city": "Islamabad",
            "province": "Punjab",
            "postal_code": "44000",
            "investment_experience": "intermediate",
            "risk_tolerance": "medium",
            "investment_goals": ["long_term", "dividend_income"],
            "income_range": "50k_100k",
        }

    def test_register_with_full_payload_creates_all_records_and_returns_tokens(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertEqual(response.data["user"]["email"], self.payload["email"])
        self.assertEqual(response.data["kyc_profile"]["city"], self.payload["city"])
        self.assertEqual(
            response.data["investment_profile"]["risk_tolerance"],
            self.payload["risk_tolerance"],
        )

        user = User.objects.get(email=self.payload["email"])
        self.assertTrue(hasattr(user, "kyc_profile"))
        self.assertTrue(hasattr(user, "investment_profile"))
        self.assertTrue(hasattr(user, "notification_preferences"))
        self.assertTrue(user.notification_preferences.email_enabled)
        self.assertTrue(user.notification_preferences.whatsapp_enabled)

    def test_register_is_atomic_when_onboarding_fields_invalid(self):
        invalid_payload = {
            **self.payload,
            "email": "atomic@example.com",
            "investment_goals": [],
        }

        response = self.client.post(self.url, invalid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("investment_goals", response.data)
        self.assertFalse(User.objects.filter(email="atomic@example.com").exists())

    def test_register_rejects_duplicate_email(self):
        first = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second_payload = {
            **self.payload,
            "first_name": "Another",
        }
        second = self.client.post(self.url, second_payload, format="json")

        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", second.data)

    def test_register_returns_access_token_with_24_hour_lifetime(self):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        token = AccessToken(response.data["tokens"]["access"])
        issued_at = timezone.datetime.fromtimestamp(token["iat"], tz=dt_timezone.utc)
        expires_at = timezone.datetime.fromtimestamp(token["exp"], tz=dt_timezone.utc)

        self.assertEqual(expires_at - issued_at, timedelta(hours=24))
