
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def send_verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)

    query = urlencode({
        "uid": uid,
        "token": token,
    })

    verification_url = (
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}"
        f"/verify-email?{query}"
    )

    send_mail(
        subject="Verify your Splitter account",
        message=(
            f"Hello {user.full_name},\n\n"
            "Welcome to Splitter!\n\n"
            "Verify your email using this link:\n"
            f"{verification_url}\n\n"
            "This link expires in 24 hours.\n"
        ),
        from_email="noreply@splitter.local",
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_reset_email(user):
    from django.contrib.auth.tokens import default_token_generator
    query = urlencode({'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                       'token': default_token_generator.make_token(user)})
    url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?{query}"
    send_mail('Reset your Splitter password',
              f'Use this link to reset your password:\n{url}\n\nIf you did not request this, ignore this email.',
              'noreply@splitter.local', [user.email], fail_silently=False)
