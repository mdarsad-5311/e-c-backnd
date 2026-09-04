from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
import logging

logger = logging.getLogger('django')
security_logger = logging.getLogger('security')

from .models import Address
from .serializers import (
    AddressSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.GenericAPIView):
    """
    API endpoint for public user registration.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'register'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_data = UserSerializer(user, context=self.get_serializer_context()).data
        logger.info(f"New user registered: {user.username}")

        return Response(
            {
                "message": "User registered successfully",
                "user": user_data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(generics.GenericAPIView):
    """
    API endpoint for authenticating users via username/email and password.
    Returns JWT access and refresh token pair alongside safe user details.
    """
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            security_logger.warning(f"Failed login attempt: {request.data.get('username') or request.data.get('email')}")
            serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user_data = UserSerializer(user, context=self.get_serializer_context()).data
        logger.info(f"User logged in: {user.username}")

        return Response(
            {
                "access": serializer.validated_data["access"],
                "refresh": serializer.validated_data["refresh"],
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(generics.GenericAPIView):
    """
    API endpoint for blacklisting the refresh token upon logout.
    """
    serializer_class = LogoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"User logged out: {request.user.username}")
            return Response(
                {"message": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for retrieving and updating the authenticated user's profile.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        if getattr(self, "swagger_fake_view", False):
            return User()
        return self.request.user


class AddressViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for managing shipping / billing addresses for the authenticated user.
    Prevents cross-user IDOR access by filtering queryset strictly to the current user.
    """
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Address.objects.none()
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        """
        Mark a specific address as the default address for the authenticated user.
        """
        address = self.get_object()
        with transaction.atomic():
            Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
            address.is_default = True
            address.save(update_fields=["is_default", "updated_at"])

        serializer = self.get_serializer(address)
        return Response(
            {
                "message": "Address set as default successfully.",
                "address": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class PasswordChangeView(generics.GenericAPIView):
    """
    API endpoint for changing the authenticated user's password.
    """
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(generics.GenericAPIView):
    """
    API endpoint to request a password reset email token.
    Safe against user enumeration.
    """
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email__iexact=email).first()

        if user and user.is_active:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_subject = "Password Reset Request"
            reset_message = (
                f"Hello {user.username},\n\n"
                f"You requested a password reset. Use the following credentials to reset your password:\n"
                f"UID: {uidb64}\n"
                f"Token: {token}\n\n"
                f"If you did not request this, please ignore this email."
            )
            send_mail(
                subject=reset_subject,
                message=reset_message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@ecommerce.local"),
                recipient_list=[user.email],
                fail_silently=True,
            )

        return Response(
            {"message": "If that email address is in our database, we have sent a password reset link to it."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    API endpoint to confirm password reset with UID, token, and new password.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response(
            {"message": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
