from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order
from payment.models import Payment

User = get_user_model()


class PaymentFailureAndStatusAPITests(TestCase):
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
            total_amount=Decimal("600.00"),
            shipping_full_name="John Doe",
            shipping_address_line1="123 Street",
            shipping_city="City",
            shipping_postal_code="12345",
        )
        self.payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            razorpay_order_id="order_rzp_status_123",
            amount=self.order.total_amount,
            status=Payment.PaymentStatus.CREATED,
        )

    # --- Failure Endpoint Tests ---
    def test_unauthenticated_failure_report_denied(self):
        response = self.client.post("/api/payments/failure/", {
            "order_id": self.order.id,
            "reason": "Dismissed popup",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_idor_cannot_report_failure_for_other_user_order(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.post("/api/payments/failure/", {
            "order_id": self.order.id,
            "reason": "Dismissed popup",
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_successful_failure_recording(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/payments/failure/", {
            "order_id": self.order.id,
            "reason": "User cancelled payment window",
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "FAILED")

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PaymentStatus.FAILED)
        self.assertEqual(self.payment.failure_reason, "User cancelled payment window")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PENDING)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

    # --- Status Endpoint Tests ---
    def test_unauthenticated_status_check_denied(self):
        response = self.client.get(f"/api/payments/status/{self.order.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_idor_cannot_check_status_of_other_user_order(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(f"/api/payments/status/{self.order.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_endpoint_returns_correct_payment_status(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/payments/status/{self.order.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Payment.PaymentStatus.CREATED)
        self.assertEqual(response.data["order_id"], self.order.id)
        self.assertEqual(response.data["payment_id"], self.payment.id)

    def test_status_endpoint_for_order_without_payment_record(self):
        new_order = Order.objects.create(
            user=self.user,
            status=Order.OrderStatus.PENDING,
            total_amount=Decimal("100.00"),
            shipping_full_name="John Doe",
            shipping_address_line1="123 Street",
            shipping_city="City",
            shipping_postal_code="12345",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/payments/status/{new_order.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Payment.PaymentStatus.PENDING)
