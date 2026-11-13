
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


class RegistrationTests(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.url = reverse("auth-register")

        self.valid_data = {
            "username": "aman_123",
            "full_name": "Aman Yadav",
            "email": "aman@example.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "upi_id": "aman@upi",
        }

    def post_registration(self, data):
        csrf_response = self.client.get(
            reverse("auth-csrf")
        )
        self.assertEqual(csrf_response.status_code, 200)

        csrf_token = self.client.cookies["csrftoken"].value

        return self.client.post(
            self.url,
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

    def test_registration_success(self):
        with self.settings(
            EMAIL_BACKEND=(
                "django.core.mail.backends.locmem.EmailBackend"
            )
        ):
            response = self.post_registration(self.valid_data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.count(), 1)

        user = User.objects.get(email="aman@example.com")

        self.assertFalse(user.email_verified)
        self.assertTrue(
            user.check_password("StrongPassword123!")
        )

        self.assertEqual(
            response.data["message"],
            "Verify your email",
        )

        self.assertNotIn("password", response.data["user"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "/verify-email?uid=",
            mail.outbox[0].body,
        )

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

    def test_password_mismatch(self):
        data = self.valid_data.copy()
        data["confirm_password"] = "DifferentPassword123!"

        response = self.post_registration(data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "VALIDATION_ERROR",
        )
        self.assertIn(
            "confirm_password",
            response.data["fields"],
        )

    def test_invalid_username(self):
        data = self.valid_data.copy()
        data["username"] = "1aman"

        response = self.post_registration(data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data["fields"])

    def test_short_password(self):
        data = self.valid_data.copy()
        data["password"] = "short"
        data["confirm_password"] = "short"

        response = self.post_registration(data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data["fields"])

    def test_duplicate_email(self):
        User.objects.create_user(
            email="aman@example.com",
            username="existing",
            full_name="Existing User",
            password="ExistingPassword123!",
        )

        response = self.post_registration(self.valid_data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data["fields"])

    def test_registration_rejects_photo_field(self):
        data = self.valid_data.copy()
        data["photo"] = "some-image.jpg"

        response = self.post_registration(data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("photo", response.data["fields"])

    def test_registration_requires_csrf(self):
        response = self.client.post(
            self.url,
            self.valid_data,
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 0)
