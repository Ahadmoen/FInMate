from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import AccessToken

from django.contrib.auth import get_user_model

from .models import DeviceToken, NotificationPreference

User = get_user_model()
from .serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    InvestmentProfileSerializer,
    NotificationPreferenceSerializer,
    RegisterSerializer,
    UserFullDetailsSerializer,
    UserKycProfileSerializer,
    UserKycUpdateSerializer,
    UserProfileSerializer,
)


class RegisterView(generics.CreateAPIView):
    """POST /api/users/register/ — open endpoint to create a new account."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
        user = serializer.save()
        # RegisterSerializer contains onboarding-only fields that are not direct
        # attributes on CustomUser, so avoid serializing `serializer.data` here.
        headers = self.get_success_headers({})

        access = AccessToken.for_user(user)
        return Response(
            {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                },
                "kyc_profile": UserKycProfileSerializer(user.kyc_profile).data,
                "investment_profile": InvestmentProfileSerializer(
                    user.investment_profile
                ).data,
                "access": str(access),
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class EmailLoginView(TokenObtainPairView):
    """POST /api/v1/login/ — obtain JWT pair via email + password."""

    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET / PUT /api/users/profile/ — view and update the current user."""

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch"]

    def get_object(self):
        return self.request.user


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """GET / PUT /api/users/notifications/ — manage notification preferences."""

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "put", "patch"]

    def get_object(self):
        prefs, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return prefs


class InvestmentProfileView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/v1/users/investment-profile/ — view and update investment preferences."""

    serializer_class = InvestmentProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user.investment_profile


class UserProfileKycUpdateView(generics.UpdateAPIView):
    """PATCH /api/v1/users/edit/ — update user details and KYC profile."""

    serializer_class = UserKycUpdateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def get_object(self):
        return self.request.user


class UserFullDetailsView(generics.RetrieveAPIView):
    """GET /api/v1/users/details/ — returns all signup details for the authenticated user."""

    serializer_class = UserFullDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CheckEmailView(APIView):
    """POST /api/users/check-email/ — returns whether an email is already registered."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        taken = User.objects.filter(email=email).exists()
        return Response({"taken": taken}, status=status.HTTP_200_OK)


class DeviceTokenView(APIView):
    """POST /api/v1/users/device-tokens/ — register or refresh an Expo push token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("token", "").strip()
        if not token:
            return Response({"detail": "token is required."}, status=status.HTTP_400_BAD_REQUEST)
        platform = request.data.get("platform", "")
        DeviceToken.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={"platform": platform},
        )
        return Response({"detail": "Token registered."}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """POST /api/users/change-password/ — verify old password and set a new one."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Incorrect password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated."}, status=status.HTTP_200_OK)
