from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from orders.models import Order
from cart.models import Cart
from accounts.models import Address
from products.models import Product
from categories.models import Category
from reviews.models import Review

User = get_user_model()

class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", email="u1@test.com", password="pwd")
        self.user2 = User.objects.create_user(username="u2", email="u2@test.com", password="pwd")
        self.staff = User.objects.create_superuser(username="admin", email="admin@test.com", password="pwd")

        self.client1 = APIClient()
        self.client1.force_authenticate(user=self.user1)
        
        self.client2 = APIClient()
        self.client2.force_authenticate(user=self.user2)

        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)

        # Setup mock data
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.product = Product.objects.create(name="Prod", slug="prod", price=100, stock=10, category=self.category)

        self.order1 = Order.objects.create(user=self.user1, status="pending", total_amount=100, subtotal=100)
        self.address1 = Address.objects.create(user=self.user1, full_name="U1", city="C1", postal_code="000")
        self.review1 = Review.objects.create(user=self.user1, product=self.product, rating=5, comment="Great")

    def test_cart_idor(self):
        # Cart ViewSet get_queryset limits to request.user
        Cart.objects.create(user=self.user1)
        res = self.client2.get("/api/cart/")
        # Client 2 should not see Client 1's cart
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data.get('items', [])), 0)

    def test_order_idor(self):
        res = self.client2.get(f"/api/orders/{self.order1.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_address_idor(self):
        res = self.client2.put(f"/api/accounts/addresses/{self.address1.id}/", {"city": "Hacked"})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_review_idor(self):
        res = self.client2.patch(f"/api/products/{self.product.id}/reviews/{self.review1.id}/", {"comment": "Hacked"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_access(self):
        res = self.client1.patch(f"/api/orders/{self.order1.id}/status/", {"status": "shipped"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.staff_client.patch(f"/api/orders/{self.order1.id}/status/", {"status": "shipped"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

class JwtSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jwtuser", email="jwt@test.com", password="pwd")
        self.client = APIClient()

    def test_token_blacklist(self):
        # Login
        res = self.client.post("/api/auth/login/", {"email": "jwt@test.com", "password": "pwd"})
        refresh_token = res.data["refresh"]

        # Logout (blacklists token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        logout_res = self.client.post("/api/auth/logout/", {"refresh": refresh_token})
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)

        # Try to use blacklisted token
        refresh_res = self.client.post("/api/auth/token/refresh/", {"refresh": refresh_token})
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

