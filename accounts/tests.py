
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase


User = get_user_model()


class UserModelTests(TestCase):

    def test_user_has_uuid_primary_key(self):
        user = User.objects.create_user(
            email="aman@example.com",
            username="aman",
            full_name="Aman",
            password="StrongTestPass123!",
        )

        self.assertEqual(user.id.version, 4)

    def test_password_is_hashed(self):
        user = User.objects.create_user(
            email="aman@example.com",
            username="aman",
            full_name="Aman",
            password="StrongTestPass123!",
        )

        self.assertNotEqual(
            user.password,
            "StrongTestPass123!",
        )
        self.assertTrue(
            user.check_password("StrongTestPass123!")
        )

    def test_email_and_username_are_normalized(self):
        user = User.objects.create_user(
            email="AMAN@EXAMPLE.COM",
            username="AMAN_123",
            full_name="Aman",
            password="StrongTestPass123!",
        )

        self.assertEqual(user.email, "aman@example.com")
        self.assertEqual(user.username, "aman_123")

    def test_new_user_is_unverified(self):
        user = User.objects.create_user(
            email="aman@example.com",
            username="aman",
            full_name="Aman",
            password="StrongTestPass123!",
        )

        self.assertFalse(user.email_verified)

    
    def test_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            email="aman@example.com",
            username="aman",
            full_name="Aman",
            password="StrongTestPass123!",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    email="AMAN@example.com",
                    username="aman2",
                    full_name="Another User",
                )
