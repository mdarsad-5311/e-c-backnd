from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for full Payment details.
    """
    user_email = serializers.EmailField(source="user.email", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "user_email",
            "order",
            "order_number",
            "razorpay_order_id",
            "razorpay_payment_id",
            "razorpay_signature",
            "amount",
            "currency",
            "status",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_email",
            "order_number",
            "created_at",
            "updated_at",
        ]


class PaymentCreateSerializer(serializers.Serializer):
    """
    Serializer to accept and validate order ID when initiating payment.
    """
    order_id = serializers.IntegerField(
        required=True,
        help_text="Primary key ID of the order to create payment for",
    )


class PaymentVerifySerializer(serializers.Serializer):
    """
    Serializer to accept and validate Razorpay verification payload.
    """
    razorpay_payment_id = serializers.CharField(
        required=True,
        max_length=255,
        help_text="Payment ID received from Razorpay Checkout",
    )
    razorpay_order_id = serializers.CharField(
        required=True,
        max_length=255,
        help_text="Order ID received from Razorpay Checkout",
    )
    razorpay_signature = serializers.CharField(
        required=True,
        max_length=255,
        help_text="HMAC SHA256 Signature received from Razorpay Checkout",
    )


class PaymentStatusSerializer(serializers.Serializer):
    """
    Serializer for payment status response.
    """
    status = serializers.CharField(
        help_text="Payment status (PENDING, CREATED, PAID, FAILED, CANCELLED, REFUNDED)"
    )
    order_id = serializers.IntegerField(required=False, help_text="Order ID")
    payment_id = serializers.IntegerField(required=False, help_text="Payment ID")


class PaymentFailureSerializer(serializers.Serializer):
    """
    Serializer for reporting a payment failure from checkout modal.
    """
    order_id = serializers.IntegerField(
        required=True,
        help_text="Primary key ID of the order whose payment failed",
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Failure or cancellation reason provided by Razorpay or user",
    )


class PaymentRetrySerializer(serializers.Serializer):
    """
    Serializer to accept order ID for retrying payment.
    """
    order_id = serializers.IntegerField(
        required=True,
        help_text="Primary key ID of the order to retry payment for",
    )
