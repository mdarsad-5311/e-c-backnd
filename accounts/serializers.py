from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from .models import Address

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer to safely expose user details."""
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = ("id", "username", "email", "first_name", "last_name")


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for retrieving and updating user profile information."""
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = ("id", "username")

    def validate_email(self, value):
        user = self.instance
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for registering a new user."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "password2", "confirm_password")
        extra_kwargs = {
            "username": {"required": True},
        }

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            data = data.copy()
        elif isinstance(data, dict):
            data = dict(data)
        if isinstance(data, dict):
            if "confirm_password" in data and "password2" not in data:
                data["password2"] = data.get("confirm_password")
            elif "password" in data and "password2" not in data:
                data["password2"] = data.get("password")
        return super().to_internal_value(data)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        password2 = attrs.get("password2") or attrs.get("confirm_password")

        if password2 and password != password2:
            raise serializers.ValidationError({"password2": "Password fields didn't match."})

        if len(password) < 8:
            raise serializers.ValidationError({"password": ["This password is too short. It must contain at least 8 characters."]})

        # Validate password using Django's configured password validators
        temp_user = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", "")
        )
        try:
            validate_password(password=password, user=temp_user)
        except DjangoValidationError as exc:
            filtered_errors = [m for m in exc.messages if "common" not in m.lower()]
            if filtered_errors:
                raise serializers.ValidationError({"password": filtered_errors})

        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        validated_data.pop("confirm_password", None)
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for authenticating users via username or email with password."""
    identifier = serializers.CharField(
        required=True,
        write_only=True,
        help_text="Username or Email address"
    )
    email = serializers.CharField(
        required=False,
        write_only=True,
        help_text="Email address"
    )
    username = serializers.CharField(
        required=False,
        write_only=True,
        help_text="Username"
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="User password"
    )

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            data = data.copy()
        elif isinstance(data, dict):
            data = dict(data)
        if isinstance(data, dict) and "identifier" not in data:
            if "email" in data and data["email"]:
                data["identifier"] = data["email"]
            elif "username" in data and data["username"]:
                data["identifier"] = data["username"]
        return super().to_internal_value(data)

    def validate(self, attrs):
        identifier = (
            attrs.get("identifier")
            or attrs.get("email")
            or attrs.get("username")
            or ""
        ).strip()
        password = attrs.get("password")

        if not identifier or not password:
            raise serializers.ValidationError("Both identifier/email/username and password are required.")

        # Lookup user by email (case-insensitive) or username (case-insensitive)
        user = None
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        
        if not user:
            user = User.objects.filter(username__iexact=identifier).first()
        
        if not user and "@" not in identifier:
            user = User.objects.filter(email__iexact=identifier).first()

        # Reject invalid credentials with uniform error message to prevent enumeration
        if not user or not user.check_password(password):
            raise exceptions.AuthenticationFailed("Invalid credentials.")

        # Reject inactive accounts
        if not user.is_active:
            raise exceptions.AuthenticationFailed("Invalid credentials.")

        # Generate SimpleJWT tokens
        refresh = RefreshToken.for_user(user)

        attrs["user"] = user
        attrs["access"] = str(refresh.access_token)
        attrs["refresh"] = str(refresh)
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Serializer for blacklisting refresh token on logout."""
    refresh = serializers.CharField(
        required=True,
        help_text="Refresh token to invalidate"
    )


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address CRUD operations."""
    class Meta:
        model = Address
        fields = (
            "id",
            "full_name",
            "phone_number",
            "street_address",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing the authenticated user's password."""
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="New password"
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="Confirm new password"
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect old password.")
        return value

    def validate(self, attrs):
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "New passwords do not match."})

        user = self.context["request"].user
        try:
            validate_password(password=new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset email."""
    email = serializers.EmailField(
        required=True,
        help_text="Email address associated with the account"
    )


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming a password reset with a valid token."""
    uidb64 = serializers.CharField(
        required=True,
        help_text="Base64-encoded user ID"
    )
    token = serializers.CharField(
        required=True,
        help_text="Password reset token"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="New password"
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="Confirm new password"
    )

    def validate(self, attrs):
        uidb64 = attrs.get("uidb64")
        token = attrs.get("token")
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})

        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})

        try:
            validate_password(password=new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        attrs["user"] = user
        return attrs
