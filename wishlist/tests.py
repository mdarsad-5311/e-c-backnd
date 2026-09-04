from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from categories.models import Category
from products.models import Product
from .models import WishlistItem

User = get_user_model()


class WishlistSystemTests(APITestCase):
    def setUp(self):
        # Users
        self.user_a = User.objects.create_user(
            username="wishuser_a", email="usera@wish.com", password="Password123!"
        )
        self.user_b = User.objects.create_user(
            username="wishuser_b", email="userb@wish.com", password="Password123!"
        )

        # Categories
        self.category = Category.objects.create(
            name="Electronics", slug="electronics", is_active=True
        )
        self.inactive_category = Category.objects.create(
            name="Legacy", slug="legacy", is_active=False
        )

        # Products
        self.prod1 = Product.objects.create(
            category=self.category,
            name="Noise Cancelling Headphones",
            slug="noise-cancelling-headphones",
            price=Decimal("199.99"),
            stock=15,
            is_active=True,
        )
        self.prod2 = Product.objects.create(
            category=self.category,
            name="Mechanical Keyboard",
            slug="mechanical-keyboard",
            price=Decimal("129.99"),
            stock=8,
            is_active=True,
        )
        self.prod_out_of_stock = Product.objects.create(
            category=self.category,
            name="Limited Edition Mouse",
            slug="limited-edition-mouse",
            price=Decimal("79.99"),
            stock=0,
            is_active=True,
        )
        self.prod_inactive = Product.objects.create(
            category=self.category,
            name="Discontinued Item",
            slug="discontinued-item",
            price=Decimal("49.99"),
            stock=5,
            is_active=False,
        )
        self.prod_inactive_cat = Product.objects.create(
            category=self.inactive_category,
            name="Legacy Cable",
            slug="legacy-cable",
            price=Decimal("19.99"),
            stock=5,
            is_active=True,
        )

        # URLs
        self.list_url = reverse("wishlist-list")
        self.add_url = reverse("wishlist-add")

    # --- 1. Authentication Tests ---
    def test_unauthenticated_wishlist_access_denied(self):
        # List
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)
        # Add
        self.assertEqual(
            self.client.post(self.add_url, {"product_id": self.prod1.id}).status_code,
            status.HTTP_401_UNAUTHORIZED
        )
        # Remove
        remove_url = reverse("wishlist-remove", kwargs={"product_id": self.prod1.id})
        self.assertEqual(self.client.delete(remove_url).status_code, status.HTTP_401_UNAUTHORIZED)
        # Move to Cart
        move_url = reverse("wishlist-move-to-cart", kwargs={"product_id": self.prod1.id})
        self.assertEqual(self.client.post(move_url).status_code, status.HTTP_401_UNAUTHORIZED)

    # --- 2. Add to Wishlist ---
    def test_add_product_to_wishlist_success(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": self.prod1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["is_already_wishlisted"])
        self.assertEqual(WishlistItem.objects.filter(user=self.user_a).count(), 1)
        self.assertEqual(response.data["item"]["product"]["id"], self.prod1.id)

    def test_add_duplicate_product_prevents_duplicate_records(self):
        self.client.force_authenticate(user=self.user_a)
        # 1st add
        res1 = self.client.post(self.add_url, {"product_id": self.prod1.id})
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # 2nd add (same product)
        res2 = self.client.post(self.add_url, {"product_id": self.prod1.id})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data["is_already_wishlisted"])
        self.assertEqual(WishlistItem.objects.filter(user=self.user_a).count(), 1)

    def test_add_nonexistent_product_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": 99999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_inactive_product_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": self.prod_inactive.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_inactive_category_product_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(self.add_url, {"product_id": self.prod_inactive_cat.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- 3. List Wishlist & Data Isolation ---
    def test_list_wishlist_returns_user_items_only(self):
        # User A adds prod1 and prod2
        WishlistItem.objects.create(user=self.user_a, product=self.prod1)
        WishlistItem.objects.create(user=self.user_a, product=self.prod2)

        # User B adds prod1
        WishlistItem.objects.create(user=self.user_b, product=self.prod1)

        # Authenticate User A
        self.client.force_authenticate(user=self.user_a)
        response_a = self.client.get(self.list_url)
        self.assertEqual(response_a.status_code, status.HTTP_200_OK)
        self.assertEqual(response_a.data["count"], 2)
        self.assertEqual(len(response_a.data["results"]), 2)

        # Authenticate User B
        self.client.force_authenticate(user=self.user_b)
        response_b = self.client.get(self.list_url)
        self.assertEqual(response_b.status_code, status.HTTP_200_OK)
        self.assertEqual(response_b.data["count"], 1)

    # --- 4. Remove from Wishlist ---
    def test_remove_product_from_wishlist_success(self):
        WishlistItem.objects.create(user=self.user_a, product=self.prod1)
        self.client.force_authenticate(user=self.user_a)

        remove_url = reverse("wishlist-remove", kwargs={"product_id": self.prod1.id})
        response = self.client.delete(remove_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(WishlistItem.objects.filter(user=self.user_a).count(), 0)

    def test_user_cannot_remove_another_user_wishlist_item(self):
        WishlistItem.objects.create(user=self.user_b, product=self.prod1)
        self.client.force_authenticate(user=self.user_a)

        remove_url = reverse("wishlist-remove", kwargs={"product_id": self.prod1.id})
        response = self.client.delete(remove_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # User B's item still exists
        self.assertTrue(WishlistItem.objects.filter(user=self.user_b, product=self.prod1).exists())

    def test_remove_nonexistent_wishlist_item_returns_404(self):
        self.client.force_authenticate(user=self.user_a)
        remove_url = reverse("wishlist-remove", kwargs={"product_id": self.prod2.id})
        response = self.client.delete(remove_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- 5. Move to Cart ---
    def test_move_to_cart_success(self):
        WishlistItem.objects.create(user=self.user_a, product=self.prod1)
        self.client.force_authenticate(user=self.user_a)

        move_url = reverse("wishlist-move-to-cart", kwargs={"product_id": self.prod1.id})
        response = self.client.post(move_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Wishlist item deleted
        self.assertFalse(WishlistItem.objects.filter(user=self.user_a, product=self.prod1).exists())

        # Cart contains item
        cart = Cart.objects.get(user=self.user_a)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().product, self.prod1)
        self.assertEqual(cart.items.first().quantity, 1)

    def test_move_out_of_stock_product_fails_and_preserves_wishlist_item(self):
        WishlistItem.objects.create(user=self.user_a, product=self.prod_out_of_stock)
        self.client.force_authenticate(user=self.user_a)

        move_url = reverse("wishlist-move-to-cart", kwargs={"product_id": self.prod_out_of_stock.id})
        response = self.client.post(move_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Wishlist item is NOT deleted
        self.assertTrue(WishlistItem.objects.filter(user=self.user_a, product=self.prod_out_of_stock).exists())
        # Cart has no item
        self.assertEqual(CartItem.objects.filter(cart__user=self.user_a).count(), 0)

    def test_user_cannot_move_another_user_wishlist_item_to_cart(self):
        WishlistItem.objects.create(user=self.user_b, product=self.prod1)
        self.client.force_authenticate(user=self.user_a)

        move_url = reverse("wishlist-move-to-cart", kwargs={"product_id": self.prod1.id})
        response = self.client.post(move_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # User B's wishlist item remains
        self.assertTrue(WishlistItem.objects.filter(user=self.user_b, product=self.prod1).exists())

    # --- 6. Database Level Constraint ---
    def test_db_unique_constraint_raises_integrity_error(self):
        WishlistItem.objects.create(user=self.user_a, product=self.prod1)
        with self.assertRaises(IntegrityError):
            WishlistItem.objects.create(user=self.user_a, product=self.prod1)
