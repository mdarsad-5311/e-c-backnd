from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from categories.models import Category
from products.models import Product
from reviews.models import Review

User = get_user_model()


class UpdateDeleteReviewAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="Password123!",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="Password123!",
        )
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Password123!",
        )
        self.category = Category.objects.create(name="Tech", slug="tech")
        self.product = Product.objects.create(
            category=self.category,
            name="Smart Watch",
            price=Decimal("200.00"),
            stock=10,
        )

        self.review = Review.objects.create(
            user=self.author,
            product=self.product,
            rating=5,
            title="Great watch",
            comment="Loved it",
            is_verified_purchase=True,
        )
        self.product.average_rating = Decimal("5.00")
        self.product.review_count = 1
        self.product.save()

    def test_unauthenticated_user_cannot_edit_review(self):
        response = self.client.patch(
            f"/api/reviews/{self.review.id}/",
            {"rating": 4},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_author_cannot_edit_review(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.patch(
            f"/api/reviews/{self.review.id}/",
            {"rating": 1, "comment": "Hacked review"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_can_edit_review_and_recalculate_rating(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(
            f"/api/reviews/{self.review.id}/",
            {"rating": 3, "comment": "Battery degrades after 1 year"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rating"], 3)

        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 3)

        self.product.refresh_from_db()
        self.assertEqual(self.product.average_rating, Decimal("3.00"))
        self.assertEqual(self.product.review_count, 1)

    def test_non_author_cannot_delete_review(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.delete(f"/api/reviews/{self.review.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_can_delete_review_and_reset_ratings(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.delete(f"/api/reviews/{self.review.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(Review.objects.filter(id=self.review.id).exists())

        self.product.refresh_from_db()
        self.assertEqual(self.product.average_rating, Decimal("0.00"))
        self.assertEqual(self.product.review_count, 0)

    def test_admin_can_edit_and_delete_any_review(self):
        self.client.force_authenticate(user=self.admin)
        # Edit
        patch_res = self.client.patch(
            f"/api/reviews/{self.review.id}/",
            {"title": "Moderated Title"},
            format="json",
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        # Delete
        del_res = self.client.delete(f"/api/reviews/{self.review.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.assertFalse(Review.objects.filter(id=self.review.id).exists())

    def test_multi_review_auto_aggregation(self):
        user2 = User.objects.create_user(username="u2", email="u2@example.com", password="P1")
        user3 = User.objects.create_user(username="u3", email="u3@example.com", password="P1")

        # Ratings: 5 (author), 5 (u2), 4 (u3) -> Average: (5+5+4)/3 = 4.67
        r2 = Review.objects.create(user=user2, product=self.product, rating=5, comment="Great")
        r3 = Review.objects.create(user=user3, product=self.product, rating=4, comment="Good")

        from reviews.utils import recalculate_product_ratings
        recalculate_product_ratings(self.product.id)

        self.product.refresh_from_db()
        self.assertEqual(self.product.review_count, 3)
        self.assertEqual(self.product.average_rating, Decimal("4.67"))

        # Delete review 3 (rating 4) -> (5+5)/2 = 5.00
        self.client.force_authenticate(user=user3)
        self.client.delete(f"/api/reviews/{r3.id}/")

        self.product.refresh_from_db()
        self.assertEqual(self.product.review_count, 2)
        self.assertEqual(self.product.average_rating, Decimal("5.00"))
