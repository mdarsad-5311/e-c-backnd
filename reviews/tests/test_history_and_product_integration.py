from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from categories.models import Category
from products.models import Product
from reviews.models import Review

User = get_user_model()


class ReviewHistoryAndProductIntegrationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="Password123!",
        )
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="Password123!",
        )
        self.category = Category.objects.create(name="Gadgets", slug="gadgets")
        self.product1 = Product.objects.create(
            category=self.category,
            name="Laptop Stand",
            price=Decimal("40.00"),
            stock=15,
        )
        self.product2 = Product.objects.create(
            category=self.category,
            name="USB Hub",
            price=Decimal("25.00"),
            stock=30,
        )

        # Seed reviews
        self.r1 = Review.objects.create(
            user=self.user1,
            product=self.product1,
            rating=5,
            title="Sturdy",
            comment="Holds my heavy laptop easily",
            is_verified_purchase=True,
        )
        self.r2 = Review.objects.create(
            user=self.user1,
            product=self.product2,
            rating=4,
            title="Useful",
            comment="Ports work fine",
            is_verified_purchase=True,
        )
        self.r3 = Review.objects.create(
            user=self.user2,
            product=self.product1,
            rating=3,
            title="Okay",
            comment="A bit bulky",
            is_verified_purchase=True,
        )

        from reviews.utils import recalculate_product_ratings
        recalculate_product_ratings(self.product1.id)
        recalculate_product_ratings(self.product2.id)

    def test_unauthenticated_my_reviews_denied(self):
        response = self.client.get("/api/my-reviews/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_sees_only_own_reviews(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/my-reviews/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data if isinstance(response.data, list) else response.data.get("results", response.data)
        self.assertEqual(len(results), 2)
        product_names = [r["product_name"] for r in results]
        self.assertIn("Laptop Stand", product_names)
        self.assertIn("USB Hub", product_names)

    def test_product_list_api_includes_ratings(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        products = response.data if isinstance(response.data, list) else response.data.get("results", response.data)
        p1 = next(p for p in products if p["id"] == self.product1.id)
        self.assertEqual(Decimal(str(p1["average_rating"])), Decimal("4.00"))
        self.assertEqual(p1["review_count"], 2)

    def test_product_detail_api_includes_latest_reviews(self):
        response = self.client.get(f"/api/products/{self.product1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        self.assertEqual(Decimal(str(data["average_rating"])), Decimal("4.00"))
        self.assertEqual(data["review_count"], 2)
        self.assertIn("latest_reviews", data)
        self.assertEqual(len(data["latest_reviews"]), 2)
        self.assertEqual(data["latest_reviews"][0]["id"], self.r3.id)
