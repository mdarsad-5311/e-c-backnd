from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from categories.models import Category
from orders.models import Order, OrderItem
from products.models import Product
from reviews.models import Review

User = get_user_model()


class CreateReviewAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="Password123!",
            first_name="Alice",
            last_name="Smith",
        )
        self.non_buyer = User.objects.create_user(
            username="nonbuyer",
            email="nonbuyer@example.com",
            password="Password123!",
        )
        self.cancelled_buyer = User.objects.create_user(
            username="cancelledbuyer",
            email="cancelled@example.com",
            password="Password123!",
        )

        self.category = Category.objects.create(name="Audio", slug="audio")
        self.product = Product.objects.create(
            category=self.category,
            name="Wireless Headphones",
            price=Decimal("150.00"),
            stock=20,
        )

        # 1. Buyer with confirmed order
        self.order = Order.objects.create(
            user=self.buyer,
            status=Order.OrderStatus.CONFIRMED,
            payment_status=Order.PaymentStatus.PAID,
            total_amount=Decimal("150.00"),
            shipping_full_name="Alice Smith",
            shipping_address_line1="123 Street",
            shipping_city="City",
            shipping_postal_code="12345",
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=1,
            subtotal=Decimal("150.00"),
        )

        # 2. Cancelled buyer order
        self.cancelled_order = Order.objects.create(
            user=self.cancelled_buyer,
            status=Order.OrderStatus.CANCELLED,
            payment_status=Order.PaymentStatus.FAILED,
            total_amount=Decimal("150.00"),
            shipping_full_name="Cancelled Buyer",
            shipping_address_line1="456 Ave",
            shipping_city="City",
            shipping_postal_code="12345",
        )
        OrderItem.objects.create(
            order=self.cancelled_order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=1,
            subtotal=Decimal("150.00"),
        )

    def test_unauthenticated_user_cannot_create_review(self):
        response = self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            {"rating": 5, "comment": "Amazing!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_buyer_cannot_review(self):
        self.client.force_authenticate(user=self.non_buyer)
        response = self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            {"rating": 5, "comment": "Looks nice, haven't bought yet."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("verified", str(response.data))

    def test_buyer_with_cancelled_order_cannot_review(self):
        self.client.force_authenticate(user=self.cancelled_buyer)
        response = self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            {"rating": 1, "comment": "Order was cancelled."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("verified", str(response.data))

    def test_verified_buyer_successful_review_creation_and_aggregation(self):
        self.client.force_authenticate(user=self.buyer)
        payload = {
            "rating": 5,
            "title": "Outstanding Sound Quality",
            "comment": "Bass is deep and battery lasts 30 hours.",
        }
        response = self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["rating"], 5)
        self.assertEqual(response.data["title"], "Outstanding Sound Quality")
        self.assertEqual(response.data["user_name"], "Alice Smith")
        self.assertTrue(response.data["is_verified_purchase"])

        # Check Product auto-aggregation
        self.product.refresh_from_db()
        self.assertEqual(self.product.average_rating, Decimal("5.00"))
        self.assertEqual(self.product.review_count, 1)
        self.assertEqual(self.product.rating, Decimal("5.00"))
        self.assertEqual(self.product.reviews_count, 1)

    def test_duplicate_review_by_same_user_blocked(self):
        self.client.force_authenticate(user=self.buyer)
        # Create first review
        self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            {"rating": 5, "comment": "First review"},
            format="json",
        )

        # Attempt second review
        response = self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            {"rating": 4, "comment": "Second review attempt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already reviewed", str(response.data).lower())

    def test_invalid_rating_rejected(self):
        self.client.force_authenticate(user=self.buyer)

        # Rating too high
        res1 = self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            {"rating": 6, "comment": "Too high"},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Rating too low
        res2 = self.client.post(
            f"/api/products/{self.product.id}/reviews/",
            {"rating": 0, "comment": "Too low"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_public_get_reviews_endpoint(self):
        # Create review directly
        Review.objects.create(
            user=self.buyer,
            product=self.product,
            rating=4,
            title="Good",
            comment="Very nice headphones",
            is_verified_purchase=True,
        )
        self.product.average_rating = Decimal("4.00")
        self.product.review_count = 1
        self.product.save()

        # Unauthenticated GET
        response = self.client.get(f"/api/products/{self.product.id}/reviews/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["average_rating"], 4.0)
        self.assertEqual(response.data["review_count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["rating"], 4)
