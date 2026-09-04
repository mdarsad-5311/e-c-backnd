from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AddressViewSet,
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    UserProfileView,
)

router = DefaultRouter()
router.register(r"addresses", AddressViewSet, basename="address")

auth_patterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]

urlpatterns = [
    # Auth endpoints
    path("auth/", include(auth_patterns)),
    # Profile endpoints
    path("profile/", UserProfileView.as_view(), name="user_profile"),
    # Addresses router endpoints
    path("", include(router.urls)),
]
