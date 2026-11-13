from django.test import TestCase
from django.urls import reverse


class CSRFEndpointTests(TestCase):

    def test_csrf_endpoint_returns_cookie(self):
        response = self.client.get(
            reverse("auth-csrf")
        )

        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(
            response.content,
            {"message": "CSRF cookie set"}
        )

        self.assertIn(
            "csrftoken",
            response.cookies
        )

    def test_csrf_endpoint_rejects_post(self):
        response = self.client.post(
            reverse("auth-csrf")
        )

        self.assertEqual(response.status_code, 405)