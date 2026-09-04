import io
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from categories.models import Category
from .models import Product, ProductImage

User = get_user_model()


def generate_test_image():
    img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return ContentFile(buffer.getvalue(), name="test.jpg")


class ProductCatalogTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminuser", email="admin@test.com", password="AdminPassword123!"
        )
        self.user = User.objects.create_user(
            username="normaluser", email="user@test.com", password="UserPassword123!"
        )

        # Categories
        self.cat_electronics = Category.objects.create(
            name="Electronics", slug="electronics", is_active=True
        )
        self.cat_fashion = Category.objects.create(
            name="Fashion", slug="fashion", is_active=True
        )
        self.cat_inactive = Category.objects.create(
            name="Inactive Cat", slug="inactive-cat", is_active=False
        )

        # Products
        self.prod1 = Product.objects.create(
            category=self.cat_electronics,
            name="Quantum Pro Wireless Headphones",
            slug="quantum-pro-wireless-headphones",
            description="Premium noise cancelling headphones with deep bass.",
            price=Decimal("299.99"),
            compare_at_price=Decimal("349.99"),
            stock=15,
            brand="Sony",
            sku="SONY-WH-001",
            rating=Decimal("4.80"),
            reviews_count=50,
            is_featured=True,
            is_active=True,
        )
        self.img1_primary = ProductImage.objects.create(
            product=self.prod1,
            image=generate_test_image(),
            alt_text="Front view",
            is_primary=True,
            sort_order=0,
        )
        self.img1_secondary = ProductImage.objects.create(
            product=self.prod1,
            image=generate_test_image(),
            alt_text="Side view",
            is_primary=False,
            sort_order=1,
        )

        self.prod2 = Product.objects.create(
            category=self.cat_electronics,
            name="Aura Studio Speaker",
            slug="aura-studio-speaker",
            description="Compact acoustic wireless speaker with high fidelity.",
            price=Decimal("149.99"),
            compare_at_price=Decimal("179.99"),
            stock=0,  # Out of stock
            brand="Aura",
            sku="AURA-SPK-002",
            rating=Decimal("4.50"),
            reviews_count=20,
            is_featured=False,
            is_active=True,
        )

        self.prod3 = Product.objects.create(
            category=self.cat_fashion,
            name="Urban Tech Hoodie",
            slug="urban-tech-hoodie",
            description="Warm oversized streetwear cotton hoodie.",
            price=Decimal("79.99"),
            compare_at_price=Decimal("99.99"),
            stock=30,
            brand="UrbanWear",
            sku="UB-HOOD-003",
            rating=Decimal("4.70"),
            reviews_count=35,
            is_featured=True,
            is_active=True,
        )

        self.prod_inactive = Product.objects.create(
            category=self.cat_electronics,
            name="Discontinued Gadget",
            slug="discontinued-gadget",
            description="Old device not sold anymore.",
            price=Decimal("49.99"),
            stock=5,
            is_active=False,
        )

    # --- 1. Product Model & Image Tests ---
    def test_product_model_str_and_properties(self):
        self.assertEqual(str(self.prod1), "Quantum Pro Wireless Headphones")
        self.assertEqual(self.prod1.title, "Quantum Pro Wireless Headphones")
        self.assertTrue(self.prod1.is_in_stock)
        self.assertFalse(self.prod2.is_in_stock)
        self.assertEqual(self.prod1.primary_image, self.img1_primary)

    def test_primary_image_exclusivity(self):
        # Setting secondary as primary should demote first image
        self.img1_secondary.is_primary = True
        self.img1_secondary.save()
        self.img1_primary.refresh_from_db()
        self.assertTrue(self.img1_secondary.is_primary)
        self.assertFalse(self.img1_primary.is_primary)

    # --- 2. Product Listing & Serializer Tests ---
    def test_list_products_public(self):
        url = reverse("product-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return paginated response with active products
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(response.data["count"], 3)  # prod1, prod2, prod3

        slugs = [p["slug"] for p in response.data["results"]]
        self.assertIn("quantum-pro-wireless-headphones", slugs)
        self.assertIn("aura-studio-speaker", slugs)
        self.assertIn("urban-tech-hoodie", slugs)
        self.assertNotIn("discontinued-gadget", slugs)

        # Check fields and aliases
        item = next(p for p in response.data["results"] if p["slug"] == "quantum-pro-wireless-headphones")
        self.assertEqual(item["name"], "Quantum Pro Wireless Headphones")
        self.assertEqual(item["title"], "Quantum Pro Wireless Headphones")
        self.assertEqual(float(item["price"]), 299.99)
        self.assertEqual(float(item["compare_at_price"]), 349.99)
        self.assertEqual(float(item["original_price"]), 349.99)
        self.assertEqual(item["discount_percentage"], 14)  # round((350-300)/350 * 100) = 14
        self.assertEqual(item["category"]["slug"], "electronics")
        self.assertIsNotNone(item["image"])

    # --- 3. Product Detail Tests ---
    def test_product_detail_by_id(self):
        url = reverse("product-detail", kwargs={"pk_or_slug": self.prod1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], self.prod1.name)
        self.assertEqual(len(response.data["images"]), 2)
        self.assertEqual(len(response.data["gallery_images"]), 2)

    def test_product_detail_by_slug(self):
        url = reverse("product-detail", kwargs={"pk_or_slug": "urban-tech-hoodie"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.prod3.id)

    def test_inactive_product_public_404(self):
        url = reverse("product-detail", kwargs={"pk_or_slug": "discontinued-gadget"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_product_404(self):
        url = reverse("product-detail", kwargs={"pk_or_slug": "non-existent-product"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- 4. Search Tests ---
    def test_search_by_name(self):
        url = f"{reverse('product-list-create')}?search=headphones"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "quantum-pro-wireless-headphones")

    def test_search_by_description(self):
        url = f"{reverse('product-list-create')}?search=streetwear"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "urban-tech-hoodie")

    def test_search_by_frontend_q_param(self):
        url = f"{reverse('product-list-create')}?q=speaker"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "aura-studio-speaker")

    # --- 5. Filtering Tests ---
    def test_filter_by_category_slug(self):
        url = f"{reverse('product-list-create')}?category=electronics"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_filter_by_category_id(self):
        url = f"{reverse('product-list-create')}?category={self.cat_fashion.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "urban-tech-hoodie")

    def test_filter_by_price_range(self):
        url = f"{reverse('product-list-create')}?min_price=100&max_price=200"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "aura-studio-speaker")

    def test_filter_by_featured(self):
        url = f"{reverse('product-list-create')}?is_featured=true"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # prod1 and prod3

    def test_filter_by_in_stock(self):
        url = f"{reverse('product-list-create')}?in_stock=true"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # prod1 (15) and prod3 (30), not prod2 (0)

    # --- 6. Sorting Tests ---
    def test_sorting_price_asc(self):
        url = f"{reverse('product-list-create')}?ordering=price"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [float(p["price"]) for p in response.data["results"]]
        self.assertEqual(prices, sorted(prices))

    def test_sorting_price_desc(self):
        url = f"{reverse('product-list-create')}?ordering=-price"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [float(p["price"]) for p in response.data["results"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_combined_search_filter_sort(self):
        url = (
            f"{reverse('product-list-create')}?"
            f"category=electronics&min_price=100&max_price=350&is_featured=true&ordering=-price"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "quantum-pro-wireless-headphones")

    # --- 7. Security & Admin Mutations ---
    def test_unauthenticated_cannot_create_product(self):
        url = reverse("product-list-create")
        data = {
            "name": "Unauthorized Product",
            "category_id": self.cat_electronics.id,
            "price": "99.99",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_create_product(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("product-list-create")
        data = {
            "name": "New Studio Monitor",
            "category_id": self.cat_electronics.id,
            "description": "Studio grade audio monitor.",
            "price": "499.00",
            "stock": 10,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "new-studio-monitor")
