from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import Address

User = get_user_model()


class UserRegistrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.register_url = reverse("register")
        self.valid_payload = {
            "username": "arsad",
            "email": "arsad@example.com",
            "password": "StrongPassword123!",
            "password2": "StrongPassword123!",
        }

    def test_01_successful_registration(self):
        """Test 1: Successful registration returns 201 and creates user with safe payload."""
        response = self.client.post(self.register_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get("message"), "User registered successfully")

        # Verify user in database
        user = User.objects.filter(username="arsad").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "arsad@example.com")

        # Verify response payload does not contain sensitive data
        user_data = response.data.get("user", {})
        self.assertEqual(user_data.get("id"), user.id)
        self.assertEqual(user_data.get("username"), "arsad")
        self.assertEqual(user_data.get("email"), "arsad@example.com")
        self.assertNotIn("password", user_data)
        self.assertNotIn("password2", user_data)
        self.assertNotIn("password_hash", user_data)
        self.assertNotIn("is_superuser", user_data)

    def test_02_password_is_hashed(self):
        """Test 2: Password is securely hashed in the database and matches check_password."""
        raw_password = "StrongPassword123!"
        response = self.client.post(self.register_url, {
            "username": "hashed_user",
            "email": "hashed@example.com",
            "password": raw_password,
            "password2": raw_password,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="hashed_user")
        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.check_password(raw_password))

    def test_03_duplicate_username(self):
        """Test 3: Reject registration with duplicate username."""
        User.objects.create_user(
            username="arsad",
            email="other@example.com",
            password="StrongPassword123!"
        )
        response = self.client.post(self.register_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_04_duplicate_email(self):
        """Test 4: Reject registration with duplicate email."""
        User.objects.create_user(
            username="existing_user",
            email="arsad@example.com",
            password="StrongPassword123!"
        )
        response = self.client.post(self.register_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_05_password_mismatch(self):
        """Test 5: Reject registration when password and password2 do not match."""
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "StrongPassword123!",
            "password2": "DifferentPassword123!",
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password2", response.data)

    def test_06_invalid_email(self):
        """Test 6: Reject registration with invalid email format."""
        payload = {
            "username": "testuser",
            "email": "not-an-email",
            "password": "StrongPassword123!",
            "password2": "StrongPassword123!",
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_07_weak_password(self):
        """Test 7: Reject registration with weak password that fails Django validators."""
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "1234567890",
            "password2": "1234567890",
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_08_missing_required_fields(self):
        """Test 8: Reject registration when required fields are missing."""
        response = self.client.post(self.register_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)
        self.assertIn("password", response.data)
        self.assertIn("password2", response.data)

    def test_09_registration_is_public(self):
        """Test 9: Registration works without Authorization header."""
        self.client.credentials()  # Ensure no auth header is set
        response = self.client.post(self.register_url, {
            "username": "public_user",
            "email": "public@example.com",
            "password": "StrongPassword123!",
            "password2": "StrongPassword123!",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_10_existing_jwt_apis_compatibility(self):
        """Test 10: Existing JWT APIs still work with users created via registration."""
        reg_response = self.client.post(self.register_url, self.valid_payload)
        self.assertEqual(reg_response.status_code, status.HTTP_201_CREATED)

        token_url = reverse("token_obtain_pair")
        token_res = self.client.post(token_url, {
            "username": "arsad",
            "password": "StrongPassword123!",
        })
        self.assertEqual(token_res.status_code, status.HTTP_200_OK)
        access_token = token_res.data["access"]
        refresh_token = token_res.data["refresh"]

        refresh_url = reverse("token_refresh")
        refresh_res = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        new_access_token = refresh_res.data["access"]
        new_refresh_token = refresh_res.data.get("refresh", refresh_token)

        verify_url = reverse("token_verify")
        verify_res = self.client.post(verify_url, {"token": new_access_token})
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)

        blacklist_url = reverse("token_blacklist")
        blacklist_res = self.client.post(blacklist_url, {"refresh": new_refresh_token})
        self.assertEqual(blacklist_res.status_code, status.HTTP_200_OK)


class UserLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.login_url = reverse("login")
        self.register_url = reverse("register")
        self.username = "arsad"
        self.email = "arsad@example.com"
        self.password = "StrongPassword123!"
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )

    def test_login_01_username_login(self):
        """Test 1: Login using username succeeds and returns access, refresh, and user data."""
        payload = {
            "identifier": self.username,
            "password": self.password,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["id"], self.user.id)
        self.assertEqual(response.data["user"]["username"], self.username)
        self.assertEqual(response.data["user"]["email"], self.email)

    def test_login_02_email_login(self):
        """Test 2: Login using email succeeds and returns JWT tokens."""
        payload = {
            "identifier": self.email,
            "password": self.password,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.email)

    def test_login_03_email_case_insensitivity(self):
        """Test 3: Email login works regardless of letter casing."""
        for email_variant in ["arsad@example.com", "ARSAD@EXAMPLE.COM", "Arsad@Example.com"]:
            payload = {
                "identifier": email_variant,
                "password": self.password,
            }
            response = self.client.post(self.login_url, payload)
            self.assertEqual(response.status_code, status.HTTP_200_OK, f"Failed for {email_variant}")
            self.assertIn("access", response.data)
            self.assertEqual(response.data["user"]["id"], self.user.id)

    def test_login_04_invalid_password(self):
        """Test 4: Correct identifier with invalid password returns 401 Unauthorized."""
        payload = {
            "identifier": self.username,
            "password": "WrongPassword123!",
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("detail"), "Invalid credentials.")
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_login_05_invalid_username(self):
        """Test 5: Non-existent username returns 401 Unauthorized without disclosing existence."""
        payload = {
            "identifier": "non_existent_user",
            "password": self.password,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("detail"), "Invalid credentials.")

    def test_login_06_invalid_email(self):
        """Test 6: Non-existent email returns 401 Unauthorized without disclosing existence."""
        payload = {
            "identifier": "nonexistent@example.com",
            "password": self.password,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("detail"), "Invalid credentials.")

    def test_login_07_inactive_user(self):
        """Test 7: Inactive user cannot log in and receives 401 Unauthorized."""
        self.user.is_active = False
        self.user.save()

        payload = {
            "identifier": self.username,
            "password": self.password,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("detail"), "Invalid credentials.")
        self.assertNotIn("access", response.data)

    def test_login_08_missing_identifier(self):
        """Test 8: Missing identifier returns 400 Bad Request."""
        payload = {
            "password": self.password,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("identifier", response.data)

    def test_login_09_missing_password(self):
        """Test 9: Missing password returns 400 Bad Request."""
        payload = {
            "identifier": self.username,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_10_safe_response(self):
        """Test 10: Response never exposes passwords, hashes, or superuser flags."""
        payload = {
            "identifier": self.username,
            "password": self.password,
        }
        response = self.client.post(self.login_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = response.data.get("user", {})
        self.assertNotIn("password", user_data)
        self.assertNotIn("password2", user_data)
        self.assertNotIn("password_hash", user_data)
        self.assertNotIn("is_superuser", user_data)

    def test_login_11_jwt_validation_and_refresh(self):
        """Test 11: JWT tokens from login can be verified and refreshed via token endpoints."""
        payload = {
            "identifier": self.username,
            "password": self.password,
        }
        login_res = self.client.post(self.login_url, payload)
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        access_token = login_res.data["access"]
        refresh_token = login_res.data["refresh"]

        # Verify access token
        verify_url = reverse("token_verify")
        verify_res = self.client.post(verify_url, {"token": access_token})
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)

        # Refresh token
        refresh_url = reverse("token_refresh")
        refresh_res = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_res.data)

    def test_login_12_existing_registration_still_works(self):
        """Test 12: Registration endpoint remains fully functional."""
        new_payload = {
            "username": "new_user_reg",
            "email": "new_user_reg@example.com",
            "password": "StrongPassword123!",
            "password2": "StrongPassword123!",
        }
        reg_res = self.client.post(self.register_url, new_payload)
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)

        # Confirm new user can login immediately
        login_res = self.client.post(self.login_url, {
            "identifier": "new_user_reg@example.com",
            "password": "StrongPassword123!",
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

    def test_login_13_existing_simplejwt_endpoints_compatibility(self):
        """Test 13: Standard SimpleJWT endpoints still work identically."""
        token_url = reverse("token_obtain_pair")
        obtain_res = self.client.post(token_url, {
            "username": self.username,
            "password": self.password,
        })
        self.assertEqual(obtain_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", obtain_res.data)
        self.assertIn("refresh", obtain_res.data)


class LogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="logout_user",
            email="logout@example.com",
            password="StrongPassword123!"
        )
        self.refresh = RefreshToken.for_user(self.user)
        self.access_token = str(self.refresh.access_token)
        self.refresh_token = str(self.refresh)
        self.logout_url = reverse("logout")

    def test_logout_01_valid_refresh_token(self):
        """Test 1: Valid refresh token blacklists token and returns 200 OK."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(self.logout_url, {"refresh": self.refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("message"), "Successfully logged out.")

        # Attempting to refresh the blacklisted token should fail
        refresh_url = reverse("token_refresh")
        refresh_res = self.client.post(refresh_url, {"refresh": self.refresh_token})
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_02_invalid_refresh_token(self):
        """Test 2: Invalid refresh token returns 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(self.logout_url, {"refresh": "invalid.jwt.token"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_logout_03_missing_refresh_token(self):
        """Test 3: Missing refresh token in payload returns 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(self.logout_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("refresh", response.data)

    def test_logout_04_unauthenticated_request(self):
        """Test 4: Unauthenticated logout request returns 401 Unauthorized."""
        response = self.client.post(self.logout_url, {"refresh": self.refresh_token})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="profile_user",
            email="profile@example.com",
            first_name="John",
            last_name="Doe",
            password="StrongPassword123!"
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            email="other@example.com",
            first_name="Jane",
            last_name="Smith",
            password="StrongPassword123!"
        )
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.profile_url = reverse("user_profile")

    def test_profile_01_get_profile(self):
        """Test 1: Authenticated user can retrieve their own profile."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.id)
        self.assertEqual(response.data["username"], "profile_user")
        self.assertEqual(response.data["email"], "profile@example.com")
        self.assertEqual(response.data["first_name"], "John")
        self.assertEqual(response.data["last_name"], "Doe")

    def test_profile_02_update_profile(self):
        """Test 2: Authenticated user can update their profile fields."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        patch_data = {
            "first_name": "Johnny",
            "last_name": "Depp",
            "email": "johnny.depp@example.com"
        }
        response = self.client.patch(self.profile_url, patch_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Johnny")
        self.assertEqual(response.data["last_name"], "Depp")
        self.assertEqual(response.data["email"], "johnny.depp@example.com")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Johnny")
        self.assertEqual(self.user.email, "johnny.depp@example.com")

    def test_profile_03_unauthenticated_access(self):
        """Test 3: Unauthenticated profile request returns 401 Unauthorized."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_04_cannot_duplicate_email(self):
        """Test 4: User cannot update their email to an existing user's email."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.patch(self.profile_url, {"email": "other@example.com"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)


class AddressManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            username="user_a",
            email="usera@example.com",
            password="StrongPassword123!"
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            email="userb@example.com",
            password="StrongPassword123!"
        )
        self.token_a = str(RefreshToken.for_user(self.user_a).access_token)
        self.token_b = str(RefreshToken.for_user(self.user_b).access_token)
        self.address_list_url = reverse("address-list")

    def test_address_01_create_address_and_auto_default(self):
        """Test 1: Creating the first address automatically sets is_default to True."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_a}")
        payload = {
            "full_name": "Arsad Khan",
            "phone_number": "+1234567890",
            "street_address": "123 Main St",
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
            "country": "USA",
        }
        response = self.client.post(self.address_list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_default"])

        # Second address created should not be default unless specified
        payload2 = {
            "full_name": "Arsad Khan 2",
            "phone_number": "+1234567890",
            "street_address": "456 Side St",
            "city": "New York",
            "state": "NY",
            "postal_code": "10002",
            "country": "USA",
        }
        response2 = self.client.post(self.address_list_url, payload2)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response2.data["is_default"])

    def test_address_02_list_and_ownership_isolation(self):
        """Test 2: Users can only list their own addresses (User isolation)."""
        addr_a = Address.objects.create(
            user=self.user_a,
            full_name="User A Address",
            street_address="100 A St",
            city="City A",
            postal_code="11111",
            country="USA"
        )
        addr_b = Address.objects.create(
            user=self.user_b,
            full_name="User B Address",
            street_address="200 B St",
            city="City B",
            postal_code="22222",
            country="USA"
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_a}")
        response = self.client.get(self.address_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], addr_a.id)

    def test_address_03_cross_user_access_prevented(self):
        """Test 3: User A cannot retrieve, update, or delete User B's address (IDOR prevention)."""
        addr_b = Address.objects.create(
            user=self.user_b,
            full_name="User B Address",
            street_address="200 B St",
            city="City B",
            postal_code="22222",
            country="USA"
        )
        detail_url = reverse("address-detail", kwargs={"pk": addr_b.id})

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_a}")
        # GET User B address
        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_404_NOT_FOUND)

        # PATCH User B address
        patch_res = self.client.patch(detail_url, {"city": "Hacked City"})
        self.assertEqual(patch_res.status_code, status.HTTP_404_NOT_FOUND)

        # DELETE User B address
        del_res = self.client.delete(detail_url)
        self.assertEqual(del_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_address_04_set_default_address(self):
        """Test 4: Setting an address as default unsets is_default on other addresses."""
        addr1 = Address.objects.create(
            user=self.user_a,
            full_name="Addr 1",
            street_address="1st Ave",
            city="NYC",
            postal_code="10001",
            country="USA",
            is_default=True
        )
        addr2 = Address.objects.create(
            user=self.user_a,
            full_name="Addr 2",
            street_address="2nd Ave",
            city="NYC",
            postal_code="10002",
            country="USA",
            is_default=False
        )

        set_default_url = reverse("address-set-default", kwargs={"pk": addr2.id})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_a}")
        response = self.client.post(set_default_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["address"]["is_default"])

        addr1.refresh_from_db()
        addr2.refresh_from_db()
        self.assertFalse(addr1.is_default)
        self.assertTrue(addr2.is_default)

    def test_address_05_unauthenticated_access(self):
        """Test 5: Unauthenticated address request returns 401."""
        response = self.client.get(self.address_list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPassword123!"
        self.user = User.objects.create_user(
            username="pwd_user",
            email="pwd@example.com",
            password=self.password
        )
        self.token = str(RefreshToken.for_user(self.user).access_token)
        self.pwd_change_url = reverse("password_change")

    def test_pwd_change_01_success(self):
        """Test 1: Authenticated user can change password successfully."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        new_pwd = "NewSecurePassword456!"
        payload = {
            "old_password": self.password,
            "new_password": new_pwd,
            "confirm_password": new_pwd,
        }
        response = self.client.post(self.pwd_change_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("message"), "Password changed successfully.")

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_pwd))

    def test_pwd_change_02_incorrect_old_password(self):
        """Test 2: Incorrect old password returns 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        payload = {
            "old_password": "WrongOldPassword!",
            "new_password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!",
        }
        response = self.client.post(self.pwd_change_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", response.data)

    def test_pwd_change_03_password_mismatch(self):
        """Test 3: New password and confirmation mismatch returns 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        payload = {
            "old_password": self.password,
            "new_password": "NewSecurePassword456!",
            "confirm_password": "DifferentPassword789!",
        }
        response = self.client.post(self.pwd_change_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data)

    def test_pwd_change_04_weak_password(self):
        """Test 4: Weak new password failing Django validators returns 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        payload = {
            "old_password": self.password,
            "new_password": "123",
            "confirm_password": "123",
        }
        response = self.client.post(self.pwd_change_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_pwd_change_05_unauthenticated_access(self):
        """Test 5: Unauthenticated password change returns 401."""
        payload = {
            "old_password": self.password,
            "new_password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!",
        }
        response = self.client.post(self.pwd_change_url, payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPassword123!"
        self.user = User.objects.create_user(
            username="reset_user",
            email="reset@example.com",
            password=self.password
        )
        self.reset_request_url = reverse("password_reset_request")
        self.reset_confirm_url = reverse("password_reset_confirm")

    def test_reset_01_request_valid_email(self):
        """Test 1: Request password reset sends an email and returns 200."""
        mail.outbox = []
        response = self.client.post(self.reset_request_url, {"email": "reset@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Password Reset Request", mail.outbox[0].subject)

    def test_reset_02_request_nonexistent_email_prevents_enumeration(self):
        """Test 2: Non-existent email returns same 200 message without sending email."""
        mail.outbox = []
        response = self.client.post(self.reset_request_url, {"email": "nonexistent@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_03_confirm_success(self):
        """Test 3: Valid reset token allows setting a new password."""
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        new_password = "BrandNewPassword123!"

        payload = {
            "uidb64": uidb64,
            "token": token,
            "new_password": new_password,
            "confirm_password": new_password,
        }
        response = self.client.post(self.reset_confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("message"), "Password has been reset successfully.")

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_reset_04_confirm_invalid_token(self):
        """Test 4: Invalid reset token returns 400 Bad Request."""
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        payload = {
            "uidb64": uidb64,
            "token": "invalid-token-123",
            "new_password": "BrandNewPassword123!",
            "confirm_password": "BrandNewPassword123!",
        }
        response = self.client.post(self.reset_confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)

    def test_reset_05_confirm_password_mismatch(self):
        """Test 5: Password confirmation mismatch returns 400 Bad Request."""
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        payload = {
            "uidb64": uidb64,
            "token": token,
            "new_password": "BrandNewPassword123!",
            "confirm_password": "DifferentPassword456!",
        }
        response = self.client.post(self.reset_confirm_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data)
