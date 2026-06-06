from django.urls import path

from .views import (
    ChangePasswordView,
    CheckEmailView,
    DeviceTokenView,
    InvestmentProfileView,
    NotificationPreferenceView,
    ProfileView,
    RegisterView,
    UserFullDetailsView,
    UserProfileKycUpdateView,
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="user-register"),
    path("check-email/", CheckEmailView.as_view(), name="user-check-email"),
    path("profile/", ProfileView.as_view(), name="user-profile"),
    path("investment-profile/", InvestmentProfileView.as_view(), name="investment-profile"),
    path("notifications/", NotificationPreferenceView.as_view(), name="user-notifications"),
    path("change-password/", ChangePasswordView.as_view(), name="user-change-password"),
    path("details/", UserFullDetailsView.as_view(), name="user-full-details"),
    path("edit/", UserProfileKycUpdateView.as_view(), name="user-profile-kyc-edit"),
    path("device-tokens/", DeviceTokenView.as_view(), name="user-device-tokens"),
]
