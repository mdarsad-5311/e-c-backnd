from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from categories.models import Category
from products.models import Product
from orders.models import Order, OrderItem

User = get_user_model()


class OrderViewSecurityAndManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.user1 = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="Password123!"
        )
        self.user2 = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="Password123!"
        )
        self.admin_user = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="AdminPassword123!"
        )

        self.category = Category.objects.create(name="Apparel", slug="apparel")
        self.product = Product.objects.create(
            category=self.category,
            name="Classic Denim Jacket",
            price=Decimal("89.99"),
            stock=15,
        )

        # Create Order for Alice
        self.order1 = Order.objects.create(
            user=self.user1,
            subtotal=Decimal("89.99"),
            total_amount=Decimal("89.99"),
            status=Order.OrderStatus.PENDING,
            shipping_full_name="Alice Smith",
            shipping_address_line1="100 Main Street",
            shipping_city="Seattle",
            shipping_postal_code="98101",
        )
        self.item1 = OrderItem.objects.create(
            order=self.order1,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=1,
            subtotal=Decimal("89.99"),
        )

        # Create Order for Bob
        self.order2 = Order.objects.create(
            user=self.user2,
            subtotal=Decimal("179.98"),
            total_amount=Decimal("179.98"),
            status=Order.OrderStatus.SHIPPED,
            shipping_full_name="Bob Jones",
            shipping_address_line1="200 Broadway",
            shipping_city="New York",
            shipping_postal_code="10001",
        )
        self.item2 = OrderItem.objects.create(
            order=self.order2,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            subtotal=Decimal("179.98"),
        )

    def test_user_only_sees_their_own_orders_in_list(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        order_ids = [o["id"] for o in response.data]
        self.assertIn(self.order1.id, order_ids)
        self.assertNotIn(self.order2.id, order_ids)

    def test_user_cannot_access_other_users_order_detail_idor_protection(self):
        self.client.force_authenticate(user=self.user1)
        # Alice tries to retrieve Bob's order
        response = self.client.get(f"/api/orders/{self.order2.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_order_detail_structure_and_timeline(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f"/api/orders/{self.order1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(data["id"], self.order1.id)
        self.assertEqual(data["order_number"], self.order1.order_number)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["title"], "Classic Denim Jacket")
        self.assertEqual(data["items"][0]["qty"], 1)
        self.assertIn("timeline", data)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["subtotal"], 89.99)

    def test_customer_can_cancel_pending_order_and_restores_stock(self):
        self.client.force_authenticate(user=self.user1)
        initial_stock = self.product.stock

        response = self.client.post(f"/api/orders/{self.order1.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["order"]["status"], "cancelled")

        # Verify stock replenished
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock + 1)

    def test_customer_cannot_cancel_shipped_order(self):
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(f"/api/orders/{self.order2.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot cancel", response.data["detail"])

    def test_public_user_cannot_update_order_status_directly(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(f"/api/orders/{self.order1.id}/status/", {"status": "delivered"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_order_status_and_tracking(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "status": "delivered",
            "tracking_number": "TRK-EXP-9999",
            "notes": "Delivered to front porch",
        }
        response = self.client.patch(f"/api/orders/{self.order1.id}/status/", payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, Order.OrderStatus.DELIVERED)
        self.assertEqual(self.order1.tracking_number, "TRK-EXP-9999")

    def test_admin_can_view_all_orders_and_filter_by_status(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Filter by shipped
        response_shipped = self.client.get("/api/orders/?status=shipped")
        self.assertEqual(response_shipped.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_shipped.data), 1)
        self.assertEqual(response_shipped.data[0]["id"], self.order2.id)
