from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order
from payment.models import Payment

User = get_user_model()


class VerifyPaymentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="Password123!",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="otheruser@example.com",
            password="Password123!",
        )
        self.order = Order.objects.create(
            user=self.user,
            status=Order.OrderStatus.PENDING,
            payment_status=Order.PaymentStatus.PENDING,
            total_amount=Decimal("350.00"),
            shipping_full_name="John Doe",
            shipping_address_line1="123 Street",
            shipping_city="City",
            shipping_postal_code="12345",
        )
        self.payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            razorpay_order_id="order_rzp_verify_123",
            amount=self.order.total_amount,
            status=Payment.PaymentStatus.CREATED,
        )

    def test_unauthenticated_verify_denied(self):
        response = self.client.post("/api/payments/verify/", {
            "razorpay_order_id": "order_rzp_verify_123",
            "razorpay_payment_id": "pay_test_456",
            "razorpay_signature": "mock_valid_signature",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_payment_not_found(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/payments/verify/", {
            "razorpay_order_id": "order_non_existent",
            "razorpay_payment_id": "pay_test_456",
            "razorpay_signature": "mock_signature",
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_idor_cannot_verify_other_user_payment(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post("/api/payments/verify/", {
            "razorpay_order_id": "order_rzp_verify_123",
            "razorpay_payment_id": "pay_test_456",
            "razorpay_signature": "mock_signature",
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("payment.views.verify_razorpay_signature", return_value=True)
    def test_successful_signature_verification(self, mock_verify):
        self.client.force_authenticate(user=self.user)
        payload = {
            "razorpay_order_id": "order_rzp_verify_123",
            "razorpay_payment_id": "pay_test_456",
            "razorpay_signature": "valid_mock_signature_hex",
        }
        response = self.client.post("/api/payments/verify/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["order_id"], self.order.id)
        self.assertEqual(response.data["payment_id"], self.payment.id)

        # Verify Payment model state
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PaymentStatus.PAID)
        self.assertEqual(self.payment.razorpay_payment_id, "pay_test_456")
        self.assertEqual(self.payment.razorpay_signature, "valid_mock_signature_hex")
        self.assertEqual(self.payment.failure_reason, "")

        # Verify Order model state updated to CONFIRMED & PAID
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.CONFIRMED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.payment_method, "Razorpay")

    @patch("payment.views.verify_razorpay_signature", return_value=False)
    def test_invalid_signature_rejection(self, mock_verify):
        self.client.force_authenticate(user=self.user)
        payload = {
            "razorpay_order_id": "order_rzp_verify_123",
            "razorpay_payment_id": "pay_forged_456",
            "razorpay_signature": "invalid_forged_signature",
        }
        response = self.client.post("/api/payments/verify/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("invalid", response.data["detail"].lower())

        # Verify Payment transitioned to FAILED
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PaymentStatus.FAILED)
        self.assertIn("Invalid signature", self.payment.failure_reason)

        # Verify Order remains PENDING
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PENDING)

    @patch("payment.views.verify_razorpay_signature", return_value=True)
    def test_duplicate_verification_blocked(self, mock_verify):
        self.client.force_authenticate(user=self.user)

        # Mark already paid
        self.payment.status = Payment.PaymentStatus.PAID
        self.payment.save()

        payload = {
            "razorpay_order_id": "order_rzp_verify_123",
            "razorpay_payment_id": "pay_test_456",
            "razorpay_signature": "valid_signature",
        }
        response = self.client.post("/api/payments/verify/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already", response.data["detail"].lower())
