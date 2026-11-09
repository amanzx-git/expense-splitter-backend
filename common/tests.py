
from django.test import TestCase, override_settings
from django.urls import reverse


class HealthCheckTests(TestCase):

    @override_settings(DEBUG=True)
    def test_health_check_returns_json(self):
        response = self.client.get(
            reverse("health-check"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @override_settings(DEBUG=False)
    def test_health_check_is_disabled_without_debug(self):
        response = self.client.get(
            reverse("health-check"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 404)
