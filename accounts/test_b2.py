import io
import tempfile
from datetime import timedelta
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from .tokens import email_verification_token

User = get_user_model()
PASSWORD = 'UnusualStrongPass491!'
NEW_PASSWORD = 'ReplacementStrongPass817!'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class B2Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(email='person@example.com', username='person', full_name='Some Person', password=PASSWORD, email_verified=True)

    def csrf(self, client=None):
        client = client or self.client
        client.get('/api/v1/auth/csrf/')
        return client.cookies['csrftoken'].value

    def post(self, route, data=None, client=None):
        client = client or self.client
        return client.post('/api/v1/' + route, data or {}, format='json', HTTP_X_CSRFTOKEN=self.csrf(client))

    def login(self, client=None):
        return self.post('auth/login/', {'email': 'PERSON@EXAMPLE.COM', 'password': PASSWORD}, client)

    def token_data(self, generator=email_verification_token):
        return {'uid': urlsafe_base64_encode(force_bytes(self.user.pk)), 'token': generator.make_token(self.user)}

    def unverify(self):
        self.user.email_verified = False
        self.user.save(update_fields=['email_verified'])

    def test_login_session_and_profile(self):
        result = self.login()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.cookies['sessionid']['httponly'])
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get('/api/v1/users/me/').data['user'], result.data['user'])
        self.assertEqual(set(result.data['user']), {'id', 'username', 'full_name', 'email', 'email_verified', 'upi_id', 'profile_photo_url'})

    def test_login_rotates_session(self):
        session = self.client.session
        session['example'] = 'value'
        session.save()
        old_key = session.session_key
        self.login()
        self.assertNotEqual(self.client.session.session_key, old_key)

    def test_bad_credentials_generic(self):
        responses = [self.post('auth/login/', {'email': email, 'password': 'WrongPassword!'}) for email in ['person@example.com', 'unknown@example.com']]
        self.assertEqual(responses[0].status_code, 401)
        self.assertEqual(responses[0].data, responses[1].data)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_login(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.login().status_code, 401)

    def test_unverified_login(self):
        self.unverify()
        response = self.login()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data, {'code': 'EMAIL_NOT_VERIFIED', 'message': 'Verify your email before signing in.'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout(self):
        self.login()
        self.assertEqual(self.post('auth/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/v1/users/me/').status_code, 401)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_public_endpoints_require_csrf(self):
        for route in ['register/', 'login/', 'verify-email/', 'resend-verification/', 'password-reset/', 'password-reset/confirm/']:
            with self.subTest(route=route):
                response = self.client.post('/api/v1/auth/' + route, {}, format='json')
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()['code'], 'CSRF_FAILED')

    def test_authenticated_unsafe_csrf(self):
        self.login()
        for method, route in [('post', 'auth/logout/'), ('patch', 'users/me/'), ('post', 'users/me/photo/')]:
            response = getattr(self.client, method)('/api/v1/' + route, {}, format='json')
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['code'], 'CSRF_FAILED')

    def test_unauthorized_endpoints(self):
        for route in ['users/me/', 'users/search/?username=pe']:
            response = self.client.get('/api/v1/' + route)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data['code'], 'AUTHENTICATION_REQUIRED')
        for route in ['users/me/photo/', 'auth/logout/']:
            self.assertEqual(self.post(route).status_code, 401)

    def test_verify_valid_and_reused(self):
        self.unverify()
        data = self.token_data()
        self.assertEqual(self.post('auth/verify-email/', data).data, {'message': 'Email verified'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.post('auth/verify-email/', data).data['code'], 'INVALID_VERIFICATION_TOKEN')

    def test_verify_invalid_uid_and_token(self):
        self.unverify()
        for data in [{'uid': 'bad', 'token': 'bad'}, {**self.token_data(), 'token': 'bad'}, {'uid': 'eA', 'token': 'bad'}]:
            self.assertEqual(self.post('auth/verify-email/', data).data['code'], 'INVALID_VERIFICATION_TOKEN')

    def test_already_verified(self):
        self.assertEqual(self.post('auth/verify-email/', self.token_data()).status_code, 400)

    def test_verify_expiry_independent_of_reset_timeout(self):
        self.unverify()
        now = email_verification_token._now()
        data = self.token_data()
        with override_settings(PASSWORD_RESET_TIMEOUT=1):
            with patch.object(email_verification_token, '_now', return_value=now + timedelta(hours=23)):
                self.assertTrue(email_verification_token.check_token(self.user, data['token']))
        with patch.object(email_verification_token, '_now', return_value=now + timedelta(hours=24, seconds=1)):
            self.assertEqual(self.post('auth/verify-email/', data).status_code, 400)

    def test_resend_generic_and_links(self):
        self.unverify()
        known = self.post('auth/resend-verification/', {'email': self.user.email})
        unknown = self.post('auth/resend-verification/', {'email': 'unknown@example.com'})
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('http://localhost:5173/verify-email?uid=', mail.outbox[0].body)
        self.user.email_verified = True
        self.user.save()
        self.post('auth/resend-verification/', {'email': self.user.email})
        self.assertEqual(len(mail.outbox), 1)

    def reset_data(self):
        return {**self.token_data(default_token_generator), 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD}

    def test_reset_request_generic_and_link(self):
        a = self.post('auth/password-reset/', {'email': self.user.email})
        b = self.post('auth/password-reset/', {'email': 'unknown@example.com'})
        self.assertEqual(a.data, b.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('http://localhost:5173/reset-password?uid=', mail.outbox[0].body)
        self.assertNotIn(PASSWORD, mail.outbox[0].body)

    def test_reset_changes_password_and_invalidates_sessions_and_token(self):
        second = APIClient(enforce_csrf_checks=True)
        self.login()
        self.login(second)
        self.user.refresh_from_db()
        data = self.reset_data()
        self.assertEqual(self.post('auth/password-reset/confirm/', data).status_code, 200)
        for client in [self.client, second]:
            self.assertEqual(client.get('/api/v1/users/me/').status_code, 401)
        self.assertEqual(self.post('auth/password-reset/confirm/', data).data['code'], 'INVALID_RESET_TOKEN')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(PASSWORD))
        self.assertEqual(self.login().status_code, 401)

    def test_reset_invalid_expired(self):
        data = self.reset_data()
        self.assertEqual(self.post('auth/password-reset/confirm/', {**data, 'token': 'bad'}).status_code, 400)
        with patch.object(default_token_generator, '_now', return_value=default_token_generator._now() + timedelta(days=2)):
            self.assertEqual(self.post('auth/password-reset/confirm/', data).data['code'], 'INVALID_RESET_TOKEN')

    def test_reset_password_validation(self):
        for password, confirmation in [('short', 'short'), ('123456789123', '123456789123'), (NEW_PASSWORD, 'different')]:
            response = self.post('auth/password-reset/confirm/', {**self.reset_data(), 'new_password': password, 'confirm_password': confirmation})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data['code'], 'VALIDATION_ERROR')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def profile_patch(self, data):
        return self.client.patch('/api/v1/users/me/', data, format='json', HTTP_X_CSRFTOKEN=self.csrf())

    def test_profile_update(self):
        self.login()
        response = self.profile_patch({'username': 'NEW_name', 'full_name': ' New Name ', 'upi_id': 'new@upi'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['user']['username'], 'new_name')
        self.assertEqual(response.data['user']['full_name'], 'New Name')

    def test_profile_protected_fields(self):
        self.login()
        for key in ['id', 'email', 'password', 'email_verified', 'is_staff', 'is_superuser', 'is_active', 'profile_photo']:
            response = self.profile_patch({key: 'anything'})
            self.assertEqual(response.status_code, 400)
            self.assertIn(key, response.data['fields'])

    def test_profile_validation(self):
        self.login()
        User.objects.create_user(email='other@example.com', username='other', full_name='Other', password=PASSWORD)
        for data in [{'username': 'OTHER'}, {'username': '1bad'}, {'upi_id': 'bad upi'}, {'full_name': ' '}, {'full_name': 'x' * 101}]:
            self.assertEqual(self.profile_patch(data).status_code, 400)
        self.assertEqual(self.profile_patch({'upi_id': ''}).status_code, 200)

    def photo(self, fmt='PNG', content=None):
        if content is None:
            output = io.BytesIO()
            Image.new('RGB', (10, 10), 'red').save(output, format=fmt)
            content = output.getvalue()
        return SimpleUploadedFile('untrusted-name.png', content, content_type='application/octet-stream')

    def upload(self, photo):
        return self.client.post('/api/v1/users/me/photo/', {'photo': photo}, format='multipart', HTTP_X_CSRFTOKEN=self.csrf())

    def test_valid_photo_formats_and_replacement_cleanup(self):
        self.login()
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            previous = None
            for fmt in ['JPEG', 'PNG', 'WEBP']:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.upload(self.photo(fmt))
                self.assertEqual(response.status_code, 200, response.data)
                self.assertTrue(response.data['profile_photo_url'].startswith('http://testserver/media/profiles/'))
                self.user.refresh_from_db()
                if previous:
                    self.assertFalse(self.user.profile_photo.storage.exists(previous))
                previous = self.user.profile_photo.name

    def test_invalid_photo_files(self):
        self.login()
        output = io.BytesIO()
        Image.new('RGB', (2, 2)).save(output, format='GIF')
        for content in [b'not an image', b'\x89PNG\r\n\x1a\ncorrupt', output.getvalue(), b'x' * (2 * 1024 * 1024 + 1)]:
            response = self.upload(self.photo(content=content))
            self.assertEqual(response.status_code, 400)
            self.assertIn('photo', response.data['fields'])

    def test_oversized_valid_image(self):
        self.login()
        output = io.BytesIO()
        Image.new('RGB', (10, 10)).save(output, format='PNG')
        self.assertEqual(self.upload(self.photo(content=output.getvalue() + b'x' * (2 * 1024 * 1024))).status_code, 400)

    def test_search_privacy_eligibility_order_limit(self):
        self.login()
        for index in range(12):
            User.objects.create_user(email=f'pe{index}@example.com', username=f'pe{index:02}', full_name='Match', password=None, email_verified=True)
        User.objects.create_user(email='hidden@example.com', username='pehidden', full_name='Hidden', password=None)
        User.objects.create_user(email='inactive@example.com', username='peinactive', full_name='Hidden', password=None, email_verified=True, is_active=False)
        response = self.client.get('/api/v1/users/search/?username=PE')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual([r['username'] for r in response.data['results']], [f'pe{i:02}' for i in range(10)])
        for row in response.data['results']:
            self.assertEqual(set(row), {'id', 'username', 'full_name'})
        self.assertEqual(self.client.get('/api/v1/users/search/?username=person').data['results'], [])

    def test_search_minimum_and_verified_requester(self):
        self.login()
        self.assertEqual(self.client.get('/api/v1/users/search/?username=p').status_code, 400)
        self.unverify()
        self.assertEqual(self.client.get('/api/v1/users/search/?username=pe').status_code, 403)

    def test_rate_limits(self):
        for route, data, count in [('auth/login/', {'email': 'nobody@example.com', 'password': 'wrong'}, 10), ('auth/resend-verification/', {'email': 'nobody@example.com'}, 5), ('auth/password-reset/', {'email': 'nobody@example.com'}, 5), ('auth/verify-email/', {'uid': 'bad', 'token': 'bad'}, 20), ('auth/password-reset/confirm/', {**self.reset_data(), 'token': 'bad'}, 20)]:
            cache.clear()
            for _ in range(count):
                self.assertNotEqual(self.post(route, data).status_code, 429)
            response = self.post(route, data)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.data['code'], 'RATE_LIMITED')
            self.assertIn('Retry-After', response)
        cache.clear()
        self.login()
        for _ in range(30):
            self.client.get('/api/v1/users/search/?username=pe')
        self.assertEqual(self.client.get('/api/v1/users/search/?username=pe').status_code, 429)

    def test_malformed_json_standard_error(self):
        response = self.client.post('/api/v1/auth/login/', '{bad', content_type='application/json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'VALIDATION_ERROR')

    def test_registration_normalization_and_duplicate_username(self):
        data = {'email': 'NEW@EXAMPLE.COM', 'username': 'NEW_user', 'full_name': ' New User ', 'password': PASSWORD, 'confirm_password': PASSWORD}
        response = self.post('auth/register/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['user']['username'], 'new_user')
        self.assertEqual(response.data['user']['email'], 'new@example.com')
        self.assertNotIn('_auth_user_id', self.client.session)
        data['email'] = 'another@example.com'
        response = self.post('auth/register/', data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.data['fields'])

    def test_registration_case_insensitive_email_duplicate(self):
        response = self.post('auth/register/', {'email': 'PERSON@EXAMPLE.COM', 'username': 'new_user', 'full_name': 'New', 'password': PASSWORD, 'confirm_password': PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data['fields'])

    def test_registration_invalid_fields(self):
        base = {'email': 'new@example.com', 'username': 'new_user', 'full_name': 'New User', 'password': PASSWORD, 'confirm_password': PASSWORD}
        for field, value in [('email', 'bad'), ('username', '_bad'), ('full_name', ' '), ('upi_id', 'bad upi'), ('password', '1234567890')]:
            data = {**base, field: value}
            if field == 'password':
                data['confirm_password'] = value
            response = self.post('auth/register/', data)
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.data['fields'])

    def test_token_purposes_are_separate(self):
        self.unverify()
        self.assertFalse(default_token_generator.check_token(self.user, email_verification_token.make_token(self.user)))
        self.assertFalse(email_verification_token.check_token(self.user, default_token_generator.make_token(self.user)))

    def test_invalid_csrf_header(self):
        self.csrf()
        response = self.client.post('/api/v1/auth/login/', {}, format='json', HTTP_X_CSRFTOKEN='x' * 32)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'CSRF_FAILED')

