
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin@example.com",
            username="adminuser",
            full_name="Admin User",
            password="StrongTestPass123!",
        )

        self.staff = User.objects.create_user(
            email="staff@example.com",
            username="staffuser",
            full_name="Staff User",
            password="StrongTestPass123!",
            is_staff=True,
        )

        self.normal_user = User.objects.create_user(
            email="normal@example.com",
            username="normaluser",
            full_name="Normal User",
            password="StrongTestPass123!",
        )

        self.list_url = reverse("admin:accounts_user_changelist")
        self.add_url = reverse("admin:accounts_user_add")
        self.change_url = reverse(
            "admin:accounts_user_change",
            args=[self.normal_user.pk],
        )
        self.delete_url = reverse(
            "admin:accounts_user_delete",
            args=[self.normal_user.pk],
        )

    def test_normal_user_cannot_access_admin(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_view_users(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_staff_with_view_permission_can_view_users(self):
        permission = Permission.objects.get(
            content_type__app_label="accounts",
            codename="view_user",
        )
        self.staff.user_permissions.add(permission)

        self.client.force_login(self.staff)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_add_users(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_change_users(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.change_url)
        self.assertEqual(response.status_code, 403)

    def test_superuser_cannot_delete_users(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 403)
