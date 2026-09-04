from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from datetime import timedelta

User = get_user_model()


class ProjectFoundationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.username = "testuser"
        self.password = "P@ssw0rd123!"
        self.user = User.objects.create_user(
            username=self.username,
            email="testuser@example.com",
            password=self.password
        )

    def test_swagger_ui_endpoint(self):
        """Test that Swagger UI endpoint is accessible."""
        response = self.client.get(reverse("schema-swagger-ui"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"swagger-ui", response.content)

    def test_redoc_endpoint(self):
        """Test that ReDoc endpoint is accessible."""
        response = self.client.get(reverse("schema-redoc"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"redoc", response.content)

    def test_swagger_schema_json(self):
        """Test that OpenAPI raw JSON schema endpoint returns valid schema."""
        response = self.client.get(reverse("schema-json", kwargs={"format": ".json"}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response["Content-Type"].startswith("application/json"))
        data = response.json()
        self.assertIn("swagger", data)
        self.assertEqual(data["info"]["title"], "E-Commerce API")

    def test_jwt_token_obtain_pair(self):
        """Test obtaining JWT access and refresh token pair."""
        url = reverse("token_obtain_pair")
        response = self.client.post(url, {
            "username": self.username,
            "password": self.password,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        # Validate access token has expected short lifespan (15 minutes Phase 9 update)
        access_token = AccessToken(response.data["access"])
        iat = access_token["iat"]
        exp = access_token["exp"]
        self.assertAlmostEqual(exp - iat, timedelta(minutes=15).total_seconds(), delta=10)

        # Validate refresh token lifetime is ~1 day
        refresh_token = RefreshToken(response.data["refresh"])
        r_exp = refresh_token["exp"]
        r_iat = refresh_token["iat"]
        self.assertAlmostEqual(r_exp - r_iat, timedelta(days=1).total_seconds(), delta=10)

    def test_jwt_token_refresh(self):
        """Test refreshing JWT access token."""
        obtain_url = reverse("token_obtain_pair")
        obtain_res = self.client.post(obtain_url, {
            "username": self.username,
            "password": self.password,
        })
        refresh_token = obtain_res.data["refresh"]

        refresh_url = reverse("token_refresh")
        refresh_res = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_res.data)
        # Token rotation is enabled, so a new refresh token is also returned
        self.assertIn("refresh", refresh_res.data)

    def test_jwt_token_verify(self):
        """Test verifying JWT access token."""
        obtain_url = reverse("token_obtain_pair")
        obtain_res = self.client.post(obtain_url, {
            "username": self.username,
            "password": self.password,
        })
        access_token = obtain_res.data["access"]

        verify_url = reverse("token_verify")
        verify_res = self.client.post(verify_url, {"token": access_token})
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)

    def test_jwt_token_blacklist(self):
        """Test blacklisting a refresh token."""
        obtain_url = reverse("token_obtain_pair")
        obtain_res = self.client.post(obtain_url, {
            "username": self.username,
            "password": self.password,
        })
        refresh_token = obtain_res.data["refresh"]

        blacklist_url = reverse("token_blacklist")
        blacklist_res = self.client.post(blacklist_url, {"refresh": refresh_token})
        self.assertEqual(blacklist_res.status_code, status.HTTP_200_OK)

        # Trying to refresh the blacklisted token should fail
        refresh_url = reverse("token_refresh")
        fail_res = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(fail_res.status_code, status.HTTP_401_UNAUTHORIZED)
