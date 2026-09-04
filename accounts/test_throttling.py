import json
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()

@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': (
            'rest_framework_simplejwt.authentication.JWTAuthentication',
        ),
        'DEFAULT_PERMISSION_CLASSES': (
            'rest_framework.permissions.IsAuthenticatedOrReadOnly',
        ),
        'DEFAULT_THROTTLE_CLASSES': [
            'rest_framework.throttling.AnonRateThrottle',
            'rest_framework.throttling.UserRateThrottle',
            'rest_framework.throttling.ScopedRateThrottle',
        ],
        'DEFAULT_THROTTLE_RATES': {
            'login': '1/minute',
            'register': '1/minute',
            'checkout': '1/minute',
            'payment_verify': '1/minute',
            'review': '1/minute',
        }
    }
)
class ThrottlingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="throttleuser", email="throttle@test.com", password="password123")
        cache.clear()

    def test_login_throttling(self):
        url = "/api/auth/login/"
        payload = {"email": "throttle@test.com", "password": "password123"}
        
        # First request should succeed
        res1 = self.client.post(url, payload)
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Second request should fail (429)
        res2 = self.client.post(url, payload)
        self.assertEqual(res2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_register_throttling(self):
        url = "/api/auth/register/"
        payload1 = {"email": "t1@test.com", "username": "t1", "password": "password123"}
        payload2 = {"email": "t2@test.com", "username": "t2", "password": "password123"}

        res1 = self.client.post(url, payload1)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post(url, payload2)
        self.assertEqual(res2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
