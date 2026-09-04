import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from orders.models import Order
from .models import Payment
from .serializers import (
    PaymentCreateSerializer,
    PaymentFailureSerializer,
    PaymentRetrySerializer,
    PaymentSerializer,
    PaymentStatusSerializer,
    PaymentVerifySerializer,
)
from .utils import get_razorpay_client, verify_razorpay_signature

logger = logging.getLogger('django')
payments_logger = logging.getLogger('payments')


class CreatePaymentOrderView(APIView):
    """
    Step 2: Create Razorpay Order
    Accepts an internal Order ID, validates ownership & amounts,
    creates a Razorpay Gateway Order, and initializes the Payment record.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=PaymentCreateSerializer,
        responses={
            200: openapi.Response("Razorpay Order Created", PaymentCreateSerializer),
            400: "Invalid Order or Already Paid",
            403: "Permission Denied",
            404: "Order Not Found",
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]

        # 1. Validate order exists
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Validate order ownership (IDOR prevention)
        if order.user != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to access this order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3. Validate order not already paid
        if order.payment_status == Order.PaymentStatus.PAID:
            return Response(
                {"detail": "Order is already paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status == Order.OrderStatus.CANCELLED:
            return Response(
                {"detail": "Cannot initiate payment for a cancelled order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Strictly compute amount from database (never trust client)
        amount_in_rupees = order.total_amount
        amount_in_paise = int(Decimal(amount_in_rupees * 100).quantize(Decimal("1")))

        if amount_in_paise <= 0:
            return Response(
                {"detail": "Order total amount must be greater than zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Create Razorpay order via SDK
        try:
            client = get_razorpay_client()
            razorpay_order_data = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": str(order.order_number),
                "notes": {
                    "order_id": str(order.id),
                    "user_id": str(request.user.id),
                    "order_number": str(order.order_number),
                },
            }
            razorpay_order = client.order.create(data=razorpay_order_data)
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            return Response(
                {"detail": f"Failed to initiate payment gateway order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 6. Save or update Payment record atomically
        with transaction.atomic():
            payment, _ = Payment.objects.update_or_create(
                order=order,
                defaults={
                    "user": request.user,
                    "razorpay_order_id": razorpay_order["id"],
                    "amount": order.total_amount,
                    "currency": "INR",
                    "status": Payment.PaymentStatus.CREATED,
                    "failure_reason": "",
                },
            )

            # Order Status Rule: Payment Created -> Order Pending
            order.status = Order.OrderStatus.PENDING
            order.payment_status = Order.PaymentStatus.PENDING
            order.save(update_fields=["status", "payment_status", "updated_at"])
            
            payments_logger.info(f"Payment initiated for Order {order.id} by User {request.user.username}")

        return Response(
            {
                "order_id": razorpay_order["id"],
                "razorpay_order_id": razorpay_order["id"],
                "db_order_id": order.id,
                "amount": amount_in_paise,
                "currency": "INR",
                "razorpay_key": getattr(settings, "RAZORPAY_KEY_ID", ""),
            },
            status=status.HTTP_200_OK,
        )


class VerifyPaymentView(APIView):
    """
    Step 4: Verify Payment Signature
    Validates Razorpay HMAC SHA256 signature, transitions Payment & Order status to PAID / CONFIRMED.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'payment_verify'

    def get_throttles(self):
        return [ScopedRateThrottle()]

    @swagger_auto_schema(
        request_body=PaymentVerifySerializer,
        responses={
            200: openapi.Response("Payment Verified", openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                },
            )),
            400: "Invalid Signature or Duplicate Payment",
            403: "Permission Denied",
            404: "Payment Order Not Found",
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = PaymentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        razorpay_payment_id = serializer.validated_data["razorpay_payment_id"]
        razorpay_order_id = serializer.validated_data["razorpay_order_id"]
        razorpay_signature = serializer.validated_data["razorpay_signature"]

        # 1. Look up Payment by razorpay_order_id
        try:
            payment = Payment.objects.select_related("order", "user").get(
                razorpay_order_id=razorpay_order_id
            )
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment record matching Razorpay Order ID was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Ownership check (IDOR prevention)
        if payment.user != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to verify this payment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3. Duplicate payment / verification check
        if payment.status == Payment.PaymentStatus.PAID:
            return Response(
                {"detail": "Payment has already been verified and processed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Verify HMAC SHA256 Signature
        is_valid = verify_razorpay_signature(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

        if not is_valid:
            payment.status = Payment.PaymentStatus.FAILED
            payment.failure_reason = "Invalid signature verification"
            payment.save(update_fields=["status", "failure_reason", "updated_at"])
            return Response(
                {
                    "success": False,
                    "detail": "Invalid payment signature.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Success State Transitions atomically
        with transaction.atomic():
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature = razorpay_signature
            payment.status = Payment.PaymentStatus.PAID
            payment.failure_reason = ""
            payment.save(
                update_fields=[
                    "razorpay_payment_id",
                    "razorpay_signature",
                    "status",
                    "failure_reason",
                    "updated_at",
                ]
            )

            # Order Status Rule: Payment Success -> Order Confirmed, Payment Status PAID
            order = payment.order
            order.status = Order.OrderStatus.CONFIRMED
            order.payment_status = Order.PaymentStatus.PAID
            order.payment_method = "Razorpay"
            order.save(update_fields=["status", "payment_status", "payment_method", "updated_at"])
            
            payments_logger.info(f"Payment success for Order {order.id} by User {request.user.username}")

        return Response(
            {
                "success": True,
                "message": "Payment verified successfully.",
                "order_id": order.id,
                "payment_id": payment.id,
            },
            status=status.HTTP_200_OK,
        )


class PaymentStatusView(APIView):
    """
    Step 6: Payment Status API
    GET /api/payments/status/<order_id>/
    Returns the real-time status of payment associated with given order.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: PaymentStatusSerializer,
            403: "Permission Denied",
            404: "Order Not Found",
        }
    )
    def get(self, request, order_id=None, *args, **kwargs):
        # 1. Fetch Order
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Ownership check
        if order.user != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to view payment status for this order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3. Retrieve associated payment
        payment = Payment.objects.filter(order=order).first()
        payment_status_val = payment.status if payment else Payment.PaymentStatus.PENDING

        return Response(
            {
                "status": payment_status_val,
                "order_id": order.id,
                "payment_id": payment.id if payment else None,
            },
            status=status.HTTP_200_OK,
        )


class PaymentFailureView(APIView):
    """
    Step 5: Failed Payment Recording
    POST /api/payments/failure/
    Records failure details from the frontend without creating duplicate orders.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=PaymentFailureSerializer,
        responses={
            200: openapi.Response("Failure recorded"),
            400: "Bad Request",
            403: "Permission Denied",
            404: "Order Not Found",
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = PaymentFailureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]
        reason = serializer.validated_data.get("reason", "")

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.user != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to access this order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            payment, _ = Payment.objects.update_or_create(
                order=order,
                defaults={
                    "user": request.user,
                    "amount": order.total_amount,
                    "currency": "INR",
                    "status": Payment.PaymentStatus.FAILED,
                    "failure_reason": reason,
                },
            )

            # Order Status Rule: Payment Failed -> Order Pending
            order.status = Order.OrderStatus.PENDING
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=["status", "payment_status", "updated_at"])
            
            payments_logger.info(f"Payment failure recorded for Order {order.id} by User {request.user.username}. Reason: {reason}")

        return Response(
            {
                "detail": "Payment failure recorded.",
                "status": Payment.PaymentStatus.FAILED,
                "order_id": order.id,
            },
            status=status.HTTP_200_OK,
        )


class RetryPaymentView(APIView):
    """
    Step 7: Retry Payment
    POST /api/payments/retry/
    Creates a fresh Razorpay order for an unpaid order and marks previous payment as FAILED.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=PaymentRetrySerializer,
        responses={
            200: openapi.Response("Fresh Razorpay Order Details"),
            400: "Order already paid or cancelled",
            403: "Permission Denied",
            404: "Order Not Found",
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = PaymentRetrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.user != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to retry payment for this order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate order not already paid
        if order.payment_status == Order.PaymentStatus.PAID:
            return Response(
                {"detail": "Order is already paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status == Order.OrderStatus.CANCELLED:
            return Response(
                {"detail": "Cannot retry payment for a cancelled order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_in_rupees = order.total_amount
        amount_in_paise = int(Decimal(amount_in_rupees * 100).quantize(Decimal("1")))

        # Create fresh Razorpay Order
        try:
            client = get_razorpay_client()
            razorpay_order_data = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": str(order.order_number),
                "notes": {
                    "order_id": str(order.id),
                    "user_id": str(request.user.id),
                    "order_number": str(order.order_number),
                    "retry": "true",
                },
            }
            razorpay_order = client.order.create(data=razorpay_order_data)
        except Exception as e:
            logger.error(f"Razorpay retry order creation failed: {e}")
            return Response(
                {"detail": f"Failed to generate retry payment order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        with transaction.atomic():
            payment, _ = Payment.objects.update_or_create(
                order=order,
                defaults={
                    "user": request.user,
                    "razorpay_order_id": razorpay_order["id"],
                    "amount": order.total_amount,
                    "currency": "INR",
                    "status": Payment.PaymentStatus.CREATED,
                    "failure_reason": "",
                },
            )

            order.status = Order.OrderStatus.PENDING
            order.payment_status = Order.PaymentStatus.PENDING
            order.save(update_fields=["status", "payment_status", "updated_at"])

        return Response(
            {
                "order_id": razorpay_order["id"],
                "razorpay_order_id": razorpay_order["id"],
                "db_order_id": order.id,
                "amount": amount_in_paise,
                "currency": "INR",
                "razorpay_key": getattr(settings, "RAZORPAY_KEY_ID", ""),
            },
            status=status.HTTP_200_OK,
        )
