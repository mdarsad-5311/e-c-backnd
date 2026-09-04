from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order
from payment.models import Payment

User = get_user_model()


class PaymentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="Password123!",
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("499.99"),
            shipping_full_name="Jane Doe",
            shipping_address_line1="123 Main St",
            shipping_city="Mumbai",
            shipping_postal_code="400001",
        )

    def test_payment_creation_and_defaults(self):
        payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            amount=self.order.total_amount,
            razorpay_order_id="order_test_123",
        )
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.order, self.order)
        self.assertEqual(payment.amount, Decimal("499.99"))
        self.assertEqual(payment.currency, "INR")
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(payment.razorpay_order_id, "order_test_123")
        self.assertEqual(payment.failure_reason, "")
        self.assertIsNotNone(payment.created_at)
        self.assertIsNotNone(payment.updated_at)

    def test_amount_in_subunits(self):
        payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            amount=Decimal("150.50"),
        )
        self.assertEqual(payment.amount_in_subunits, 15050)

    def test_payment_str_representation(self):
        payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            amount=Decimal("500.00"),
            status=Payment.PaymentStatus.PAID,
        )
        self.assertIn(f"Payment #{payment.id}", str(payment))
        self.assertIn("PAID", str(payment))
        self.assertIn("INR 500.00", str(payment))

    def test_payment_status_choices(self):
        valid_statuses = [
            Payment.PaymentStatus.PENDING,
            Payment.PaymentStatus.CREATED,
            Payment.PaymentStatus.PAID,
            Payment.PaymentStatus.FAILED,
            Payment.PaymentStatus.CANCELLED,
            Payment.PaymentStatus.REFUNDED,
        ]
        for s in valid_statuses:
            self.payment = Payment.objects.create(
                user=self.user,
                order=Order.objects.create(
                    user=self.user,
                    total_amount=Decimal("10.00"),
                    shipping_full_name="A",
                    shipping_address_line1="B",
                    shipping_city="C",
                    shipping_postal_code="1",
                ),
                amount=Decimal("10.00"),
                status=s,
            )
            self.assertEqual(self.payment.status, s)
