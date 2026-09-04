from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from categories.models import Category
from products.models import Product
from reviews.models import Review

User = get_user_model()


class ReviewModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="Password123!",
            first_name="Jane",
            last_name="Doe",
        )
        self.category = Category.objects.create(name="Footwear", slug="footwear")
        self.product = Product.objects.create(
            category=self.category,
            name="Running Shoes",
            price=Decimal("99.99"),
            stock=10,
        )

    def test_review_creation_and_properties(self):
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            rating=5,
            title="Super comfortable!",
            comment="I run 5 miles every day in these.",
            is_verified_purchase=True,
        )
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.product, self.product)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.user_name, "Jane Doe")
        self.assertTrue(review.is_verified_purchase)
        self.assertIn("Jane Doe's 5★ review for Running Shoes", str(review))


    def test_unique_user_product_constraint(self):
        Review.objects.create(
            user=self.user,
            product=self.product,
            rating=4,
            comment="First review",
        )
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                user=self.user,
                product=self.product,
                rating=5,
                comment="Duplicate review attempt",
            )
