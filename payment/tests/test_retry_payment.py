from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order
from payment.models import Payment

User = get_user_model()


class RetryPaymentAPITests(TestCase):
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
            payment_status=Order.PaymentStatus.FAILED,
            total_amount=Decimal("450.00"),
            shipping_full_name="John Doe",
            shipping_address_line1="123 Street",
            shipping_city="City",
            shipping_postal_code="12345",
        )
        self.payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            razorpay_order_id="order_old_failed_123",
            amount=self.order.total_amount,
            status=Payment.PaymentStatus.FAILED,
            failure_reason="User cancelled popup",
        )

    def test_unauthenticated_retry_denied(self):
        response = self.client.post("/api/payments/retry/", {"order_id": self.order.id})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_idor_cannot_retry_other_users_order(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post("/api/payments/retry/", {"order_id": self.order.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("payment.views.get_razorpay_client")
    def test_successful_payment_retry(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {
            "id": "order_rzp_retry_999",
            "amount": 45000,
            "currency": "INR",
            "receipt": self.order.order_number,
        }
        mock_get_client.return_value = mock_client

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/payments/retry/",
            {"order_id": self.order.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["order_id"], "order_rzp_retry_999")
        self.assertEqual(response.data["razorpay_order_id"], "order_rzp_retry_999")
        self.assertEqual(response.data["amount"], 45000)

        # Verify Payment model refreshed with new razorpay order ID and status CREATED
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.razorpay_order_id, "order_rzp_retry_999")
        self.assertEqual(self.payment.status, Payment.PaymentStatus.CREATED)
        self.assertEqual(self.payment.failure_reason, "")

        # Verify Order state remains PENDING
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PENDING)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

    def test_cannot_retry_already_paid_order(self):
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/payments/retry/",
            {"order_id": self.order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already paid", response.data["detail"].lower())

    def test_cannot_retry_cancelled_order(self):
        self.order.status = Order.OrderStatus.CANCELLED
        self.order.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/payments/retry/",
            {"order_id": self.order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cancelled", response.data["detail"].lower())
