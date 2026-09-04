from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from categories.models import Category
from products.models import Product
from orders.models import Order, OrderItem

User = get_user_model()


class OrderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="Password123!"
        )
        self.category = Category.objects.create(name="Audio", slug="audio")
        self.product = Product.objects.create(
            category=self.category,
            name="Pro Wireless Headphones",
            price=Decimal("199.99"),
            stock=10,
        )

    def test_order_creation_and_defaults(self):
        order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("199.99"),
            shipping_cost=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("199.99"),
            shipping_full_name="John Doe",
            shipping_phone="+1 555-123-4567",
            shipping_address_line1="123 Tech Blvd",
            shipping_city="San Francisco",
            shipping_state="CA",
            shipping_postal_code="94105",
            shipping_country="United States",
        )
        self.assertTrue(order.order_number.startswith("ORD-"))
        self.assertTrue(order.tracking_number.startswith("TRK-"))
        self.assertEqual(order.status, Order.OrderStatus.PENDING)
        self.assertEqual(order.total_amount, Decimal("199.99"))
        self.assertIn("123 Tech Blvd", order.formatted_address)

    def test_order_item_snapshot_and_properties(self):
        order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("399.98"),
            total_amount=Decimal("399.98"),
            shipping_full_name="John Doe",
            shipping_address_line1="123 Tech Blvd",
            shipping_city="San Francisco",
            shipping_postal_code="94105",
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_sku="SKU-123",
            unit_price=self.product.price,
            quantity=2,
            subtotal=Decimal("399.98"),
        )
        self.assertEqual(item.title, "Pro Wireless Headphones")
        self.assertEqual(item.price, Decimal("199.99"))
        self.assertEqual(item.qty, 2)
        self.assertEqual(item.subtotal, Decimal("399.98"))

        # Alter original catalog product price and name to ensure historical snapshot immutability
        self.product.price = Decimal("299.99")
        self.product.name = "Pro Wireless Headphones v2"
        self.product.save()

        # Item snapshot must remain unchanged
        item.refresh_from_db()
        self.assertEqual(item.product_name, "Pro Wireless Headphones")
        self.assertEqual(item.unit_price, Decimal("199.99"))
        self.assertEqual(item.subtotal, Decimal("399.98"))
