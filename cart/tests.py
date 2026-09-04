from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from categories.models import Category
from products.models import Product
from .models import Cart, CartItem

User = get_user_model()


class CartSystemTests(APITestCase):
    def setUp(self):
        # Users
        self.user_a = User.objects.create_user(
            username="usera", email="usera@test.com", password="Password123!"
        )
        self.user_b = User.objects.create_user(
            username="userb", email="userb@test.com", password="Password123!"
        )

        # Categories
        self.category = Category.objects.create(
            name="Tech", slug="tech", is_active=True
        )
        self.inactive_category = Category.objects.create(
            name="Archived", slug="archived", is_active=False
        )

        # Products
        self.prod1 = Product.objects.create(
            category=self.category,
            name="Wireless Headphones",
            slug="wireless-headphones",
            price=Decimal("100.00"),
            compare_at_price=Decimal("150.00"),
            stock=10,
            is_active=True,
        )
        self.prod2 = Product.objects.create(
            category=self.category,
            name="Smart Watch",
            slug="smart-watch",
            price=Decimal("200.00"),
            compare_at_price=Decimal("250.00"),
            stock=5,
            is_active=True,
        )
        self.prod_out_of_stock = Product.objects.create(
            category=self.category,
            name="Limited Edition Gadget",
            slug="limited-edition-gadget",
            price=Decimal("300.00"),
            stock=0,
            is_active=True,
        )
        self.prod_inactive = Product.objects.create(
            category=self.category,
            name="Disabled Product",
            slug="disabled-product",
            price=Decimal("50.00"),
            stock=10,
            is_active=False,
        )
        self.prod_inactive_cat = Product.objects.create(
            category=self.inactive_category,
            name="Archived Product",
            slug="archived-product",
            price=Decimal("80.00"),
            stock=10,
            is_active=True,
        )

        # URLs
        self.cart_url = reverse("cart-detail")
        self.add_url = reverse("cart-add")
        self.clear_url = reverse("cart-clear")

    # --- 1. Authentication & Security ---
    def test_unauthenticated_cart_access_denied(self):
        # View
        self.assertEqual(self.client.get(self.cart_url).status_code, status.HTTP_401_UNAUTHORIZED)
        # Add
        self.assertEqual(
            self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 1}).status_code,
            status.HTTP_401_UNAUTHORIZED
        )
        # Clear
        self.assertEqual(self.client.delete(self.clear_url).status_code, status.HTTP_401_UNAUTHORIZED)

    # --- 2. Cart Retrieval & Auto-Creation ---
    def test_authenticated_user_gets_empty_cart(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.cart_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items_count"], 0)
        self.assertEqual(float(response.data["subtotal"]), 0.00)
        self.assertEqual(len(response.data["items"]), 0)

    # --- 3. Add to Cart ---
    def test_add_product_to_cart_success(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items_count"], 2)
        self.assertEqual(response.data["unique_items_count"], 1)
        self.assertEqual(float(response.data["subtotal"]), 200.00)  # 2 * 100
        self.assertEqual(float(response.data["total_original_price"]), 300.00)  # 2 * 150
        self.assertEqual(float(response.data["total_savings"]), 100.00)  # 300 - 200

    def test_add_duplicate_product_increments_quantity(self):
        self.client.force_authenticate(user=self.user_a)
        # Add 1st time
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        # Add 2nd time
        response = self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items_count"], 5)
        self.assertEqual(response.data["unique_items_count"], 1)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user_a).count(), 1)
        self.assertEqual(CartItem.objects.get(cart__user=self.user_a).quantity, 5)

    def test_add_product_exceeding_stock_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        # prod1 has stock 10
        response = self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 15})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_out_of_stock_product_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": self.prod_out_of_stock.id, "quantity": 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_inactive_product_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": self.prod_inactive.id, "quantity": 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_inactive_category_product_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": self.prod_inactive_cat.id, "quantity": 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_nonexistent_product_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": 99999, "quantity": 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- 4. Update Quantity ---
    def test_update_quantity_success(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        item = CartItem.objects.get(cart__user=self.user_a)

        update_url = reverse("cart-update", kwargs={"item_id": item.id})
        response = self.client.patch(update_url, {"quantity": 4})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items_count"], 4)
        self.assertEqual(float(response.data["subtotal"]), 400.00)

    def test_update_quantity_zero_or_negative_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        item = CartItem.objects.get(cart__user=self.user_a)

        update_url = reverse("cart-update", kwargs={"item_id": item.id})
        # Zero
        res_zero = self.client.patch(update_url, {"quantity": 0})
        self.assertEqual(res_zero.status_code, status.HTTP_400_BAD_REQUEST)
        # Negative
        res_neg = self.client.patch(update_url, {"quantity": -3})
        self.assertEqual(res_neg.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_quantity_exceeding_stock_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        item = CartItem.objects.get(cart__user=self.user_a)

        update_url = reverse("cart-update", kwargs={"item_id": item.id})
        response = self.client.patch(update_url, {"quantity": 20})  # stock is 10
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- 5. Remove Item ---
    def test_remove_cart_item_success(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        self.client.post(self.add_url, {"product_id": self.prod2.id, "quantity": 1})
        self.assertEqual(CartItem.objects.filter(cart__user=self.user_a).count(), 2)

        item1 = CartItem.objects.filter(cart__user=self.user_a, product=self.prod1).first()
        remove_url = reverse("cart-remove", kwargs={"item_id": item1.id})
        response = self.client.delete(remove_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items_count"], 1)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user_a).count(), 1)

    # --- 6. Clear Cart ---
    def test_clear_cart_success(self):
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        self.client.post(self.add_url, {"product_id": self.prod2.id, "quantity": 1})
        self.assertEqual(CartItem.objects.filter(cart__user=self.user_a).count(), 2)

        response = self.client.delete(self.clear_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items_count"], 0)
        self.assertEqual(len(response.data["items"]), 0)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user_a).count(), 0)

    # --- 7. Cross-User Security & Isolation ---
    def test_user_cannot_access_or_modify_other_user_cart(self):
        # User A adds an item
        self.client.force_authenticate(user=self.user_a)
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2})
        item_a = CartItem.objects.get(cart__user=self.user_a)

        # User B logs in
        self.client.force_authenticate(user=self.user_b)
        # User B views own cart -> should be empty
        res_b = self.client.get(self.cart_url)
        self.assertEqual(res_b.data["total_items_count"], 0)

        # User B tries to update User A's item -> 404
        update_url = reverse("cart-update", kwargs={"item_id": item_a.id})
        res_update = self.client.patch(update_url, {"quantity": 5})
        self.assertEqual(res_update.status_code, status.HTTP_404_NOT_FOUND)
        item_a.refresh_from_db()
        self.assertEqual(item_a.quantity, 2)  # Unchanged

        # User B tries to delete User A's item -> 404
        remove_url = reverse("cart-remove", kwargs={"item_id": item_a.id})
        res_remove = self.client.delete(remove_url)
        self.assertEqual(res_remove.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(CartItem.objects.filter(id=item_a.id).exists())  # Not deleted

        # User B clears own cart -> User A's cart untouched
        self.client.delete(self.clear_url)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user_a).count(), 1)

    # --- 8. Price Calculation Integrity (Server-side) ---
    def test_client_cannot_override_price(self):
        self.client.force_authenticate(user=self.user_a)
        # Attempt to pass fake low price
        self.client.post(self.add_url, {"product_id": self.prod1.id, "quantity": 2, "price": 1.00})
        item = CartItem.objects.get(cart__user=self.user_a)
        # Server calculates based on database product.price (100.00 * 2 = 200.00)
        self.assertEqual(float(item.subtotal), 200.00)
