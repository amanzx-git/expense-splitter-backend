
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.core.exceptions import ValidationError


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

class UserR12ValidationTests(TestCase):

    def test_valid_username_with_underscore_and_digits(self):
        user = User.objects.create_user(
            email="aman@example.com",
            username="aman_123",
            full_name="Aman Yadav",
            password="StrongTestPass123!",
        )

        self.assertEqual(user.username, "aman_123")

    def test_username_cannot_start_with_digit(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                email="digit@example.com",
                username="1aman",
                full_name="Digit User",
                password="StrongTestPass123!",
            )

    def test_username_cannot_start_with_underscore(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                email="underscore@example.com",
                username="_aman",
                full_name="Underscore User",
                password="StrongTestPass123!",
            )

    def test_full_name_is_trimmed(self):
        user = User.objects.create_user(
            email="trim@example.com",
            username="trimuser",
            full_name="  Aman Yadav  ",
            password="StrongTestPass123!",
        )

        self.assertEqual(user.full_name, "Aman Yadav")

    def test_full_name_cannot_exceed_100_characters(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                email="longname@example.com",
                username="longname",
                full_name="A" * 101,
                password="StrongTestPass123!",
            )
