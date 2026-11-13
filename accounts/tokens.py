from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'accounts.EmailVerificationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{timestamp}{user.email_verified}{user.email}{user.password}{user.last_login}'

    def check_token(self, user, token):
        if not user or user.email_verified or not token:
            return False
        try:
            timestamp = base36_to_int(token.split('-')[0])
        except (ValueError, TypeError):
            return False
        age = self._num_seconds(self._now()) - timestamp
        return 0 <= age <= settings.EMAIL_VERIFICATION_TIMEOUT_SECONDS and any(
            constant_time_compare(self._make_token_with_timestamp(user, timestamp, secret), token)
            for secret in [self.secret, *self.secret_fallbacks]
        )


email_verification_token = EmailVerificationTokenGenerator()
