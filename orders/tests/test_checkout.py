from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Address
from cart.models import Cart, CartItem
from categories.models import Category
from products.models import Product
from orders.models import Order, OrderItem

User = get_user_model()


class CheckoutAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="shopper",
            email="shopper@example.com",
            password="Password123!"
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="Password123!"
        )

        self.category = Category.objects.create(name="Electronics", slug="electronics")
        self.product1 = Product.objects.create(
            category=self.category,
            name="Mechanical Keyboard",
            price=Decimal("120.00"),
            stock=10,
            is_active=True,
        )
        self.product2 = Product.objects.create(
            category=self.category,
            name="Ergonomic Mouse",
            price=Decimal("60.00"),
            stock=5,
            is_active=True,
        )

        self.address = Address.objects.create(
            user=self.user,
            full_name="Shopper Doe",
            phone_number="+1 555-010-9999",
            street_address="789 Market Street",
            city="San Francisco",
            state="CA",
            postal_code="94103",
            country="United States",
            is_default=True,
        )
        self.other_address = Address.objects.create(
            user=self.other_user,
            full_name="Other Doe",
            street_address="999 Fake Street",
            city="New York",
            postal_code="10001",
        )

    def test_unauthenticated_checkout_denied(self):
        response = self.client.post("/api/orders/", {
            "shipping_address_id": self.address.id
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_cart_checkout_fails(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/orders/", {
            "shipping_address_id": self.address.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("empty", response.data["detail"].lower())

    def test_successful_checkout_with_saved_address(self):
        self.client.force_authenticate(user=self.user)

        # Seed user cart
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=2) # 2 * 120 = 240
        CartItem.objects.create(cart=cart, product=self.product2, quantity=1) # 1 * 60 = 60
        # Expected subtotal = 300.00

        payload = {
            "shipping_address_id": self.address.id,
            "payment_method": "card",
            "notes": "Please ring the bell",
        }

        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data

        self.assertEqual(Decimal(str(data["subtotal"])), Decimal("300.00"))
        self.assertEqual(Decimal(str(data["total_amount"])), Decimal("300.00"))
        self.assertEqual(data["items_count"], 2)
        self.assertEqual(data["total_quantity"], 3)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["shipping_address"]["name"], "Shopper Doe")
        self.assertEqual(data["shipping_address"]["line1"], "789 Market Street")

        # Verify stock was decremented
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock, 8)
        self.assertEqual(self.product2.stock, 4)

        # Verify cart was cleared
        cart.refresh_from_db()
        self.assertEqual(cart.items.count(), 0)

    def test_successful_checkout_with_inline_address(self):
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=1)

        payload = {
            "shipping_address": {
                "name": "Jane Doe",
                "line1": "456 Innovation Way",
                "line2": "Suite 300",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "country": "United States",
                "phone": "+1 555-888-9999",
            },
            "payment_method": "apple",
        }

        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data

        self.assertEqual(data["shipping_address"]["name"], "Jane Doe")
        self.assertEqual(data["shipping_address"]["line1"], "456 Innovation Way")
        self.assertEqual(data["payment_method"], "apple")

    def test_client_cannot_manipulate_order_prices(self):
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=1)

        # Attacker attempts to pass forged prices and totals in request
        payload = {
            "shipping_address_id": self.address.id,
            "subtotal": "1.00",
            "total_amount": "1.00",
            "unit_price": "0.50",
        }

        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data

        # Backend must enforce actual catalog price ($120.00)
        self.assertEqual(Decimal(str(data["subtotal"])), Decimal("120.00"))
        self.assertEqual(Decimal(str(data["total_amount"])), Decimal("120.00"))

    def test_user_cannot_use_other_users_address_id(self):
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=1)

        payload = {
            "shipping_address_id": self.other_address.id
        }

        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("shipping_address_id", response.data)

    def test_insufficient_stock_fails_checkout(self):
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        # Attempt to order 20 units when only 10 available
        CartItem.objects.create(cart=cart, product=self.product1, quantity=20)

        payload = {"shipping_address_id": self.address.id}
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Insufficient stock", response.data["detail"])

        # Verify stock and cart remained intact
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 10)
        self.assertEqual(cart.items.count(), 1)

    def test_inactive_product_fails_checkout(self):
        self.client.force_authenticate(user=self.user)

        self.product1.is_active = False
        self.product1.save()

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=1)

        payload = {"shipping_address_id": self.address.id}
        response = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unavailable", response.data["detail"].lower())

    def test_atomic_rollback_on_unexpected_failure(self):
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=2)

        # Mock OrderItem.objects.bulk_create to raise an exception
        with patch("orders.models.OrderItem.objects.bulk_create", side_effect=Exception("Database failure")):
            with self.assertRaises(Exception):
                self.client.post("/api/orders/", {"shipping_address_id": self.address.id}, format="json")

        # Verify no order was created, product stock was not changed, and cart was not cleared
        self.assertEqual(Order.objects.count(), 0)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 10)
        self.assertEqual(cart.items.count(), 1)
