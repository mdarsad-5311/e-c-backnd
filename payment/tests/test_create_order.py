from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order
from payment.models import Payment

User = get_user_model()


class CreatePaymentOrderAPITests(TestCase):
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
            total_amount=Decimal("500.00"),
            shipping_full_name="John Doe",
            shipping_address_line1="123 Street",
            shipping_city="City",
            shipping_postal_code="12345",
        )
        self.other_order = Order.objects.create(
            user=self.other_user,
            status=Order.OrderStatus.PENDING,
            payment_status=Order.PaymentStatus.PENDING,
            total_amount=Decimal("200.00"),
            shipping_full_name="Other Doe",
            shipping_address_line1="456 Ave",
            shipping_city="City",
            shipping_postal_code="67890",
        )

    def test_unauthenticated_request_denied(self):
        response = self.client.post("/api/payments/create-order/", {"order_id": self.order.id})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_order_not_found(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/payments/create-order/", {"order_id": 99999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "Order not found.")

    def test_idor_user_cannot_create_payment_for_other_user_order(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/payments/create-order/", {"order_id": self.other_order.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("permission", response.data["detail"].lower())

    @patch("payment.views.get_razorpay_client")
    def test_successful_razorpay_order_creation(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {
            "id": "order_rzp_mock_12345",
            "entity": "order",
            "amount": 50000,
            "amount_paid": 0,
            "amount_due": 50000,
            "currency": "INR",
            "receipt": self.order.order_number,
            "status": "created",
        }
        mock_get_client.return_value = mock_client

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/payments/create-order/",
            {"order_id": self.order.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["order_id"], "order_rzp_mock_12345")
        self.assertEqual(response.data["razorpay_order_id"], "order_rzp_mock_12345")
        self.assertEqual(response.data["amount"], 50000)
        self.assertEqual(response.data["currency"], "INR")
        self.assertTrue(len(response.data["razorpay_key"]) > 0)

        # Verify Payment model updated
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.razorpay_order_id, "order_rzp_mock_12345")
        self.assertEqual(payment.status, Payment.PaymentStatus.CREATED)
        self.assertEqual(payment.amount, Decimal("500.00"))

        # Verify Order state updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PENDING)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

        # Verify SDK called with server amount (50000 paise)
        mock_client.order.create.assert_called_once()
        call_data = mock_client.order.create.call_args[1]["data"]
        self.assertEqual(call_data["amount"], 50000)
        self.assertEqual(call_data["currency"], "INR")

    def test_cannot_create_payment_for_already_paid_order(self):
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/payments/create-order/",
            {"order_id": self.order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already paid", response.data["detail"].lower())

    def test_cannot_create_payment_for_cancelled_order(self):
        self.order.status = Order.OrderStatus.CANCELLED
        self.order.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/payments/create-order/",
            {"order_id": self.order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cancelled", response.data["detail"].lower())
