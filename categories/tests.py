from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category

User = get_user_model()


class CategoryModelAndAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="user@test.com",
            password="Password123!"
        )
        self.admin_user = User.objects.create_superuser(
            username="adminuser",
            email="admin@test.com",
            password="AdminPassword123!"
        )
        self.cat1 = Category.objects.create(
            name="Electronics",
            slug="electronics",
            description="Electronic devices and accessories",
            icon="Monitor",
            is_active=True
        )
        self.cat2 = Category.objects.create(
            name="Fashion",
            slug="fashion",
            description="Trendy clothing",
            icon="Shirt",
            is_active=True
        )
        self.cat_inactive = Category.objects.create(
            name="Archived Goods",
            slug="archived-goods",
            description="Inactive items",
            is_active=False
        )

    def test_category_creation_and_str(self):
        self.assertEqual(str(self.cat1), "Electronics")
        self.assertEqual(self.cat1.slug, "electronics")

    def test_category_slug_auto_generation(self):
        cat = Category.objects.create(name="Home & Kitchen")
        self.assertEqual(cat.slug, "home-kitchen")

    def test_category_slug_collision_handling(self):
        cat_dup = Category.objects.create(name="Electronics Dupe", slug="electronics")
        self.assertEqual(cat_dup.slug, "electronics-1")

    def test_list_active_categories_public(self):
        url = reverse("category-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only list active categories (cat1 and cat2)
        slugs = [c["slug"] for c in response.data]
        self.assertIn("electronics", slugs)
        self.assertIn("fashion", slugs)
        self.assertNotIn("archived-goods", slugs)

    def test_retrieve_category_by_id(self):
        url = reverse("category-detail", kwargs={"pk_or_slug": self.cat1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Electronics")
        self.assertEqual(response.data["slug"], "electronics")

    def test_retrieve_category_by_slug(self):
        url = reverse("category-detail", kwargs={"pk_or_slug": "fashion"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.cat2.id)

    def test_inactive_category_public_404(self):
        url = reverse("category-detail", kwargs={"pk_or_slug": "archived-goods"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_user_cannot_create_category(self):
        url = reverse("category-list-create")
        data = {"name": "New Category", "slug": "new-category"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_user_can_create_category(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("category-list-create")
        data = {"name": "Books", "description": "Books and magazines"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "books")
