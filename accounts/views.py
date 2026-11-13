from uuid import uuid4

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET
from rest_framework import serializers, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import send_password_reset_email, send_verification_email
from .serializers import (
    EmailSerializer, LoginSerializer, PhotoSerializer, ProfileSerializer,
    RegistrationSerializer, ResetConfirmSerializer, TokenSerializer, UserSerializer,
)
from .throttles import AccountsThrottle
from .tokens import email_verification_token

User = get_user_model()


@require_GET
@ensure_csrf_cookie
def csrf_token_view(request):
    return JsonResponse({
        "message": "CSRF cookie set"
    })


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser]
    throttle_classes = [AccountsThrottle]
    throttle_scope = 'register'

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Please correct the highlighted fields.",
                    "fields": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user = serializer.save()
        except (IntegrityError, DjangoValidationError):
            return Response(
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Please correct the highlighted fields.",
                    "fields": {
                        "non_field_errors": [
                            "Email or username is already registered."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_verification_email(user)

        return Response(
            {
                "user": UserSerializer(
                    user,
                    context={"request": request},
                ).data,
                "message": "Verify your email",
            },
            status=status.HTTP_201_CREATED,
        )

@method_decorator(csrf_protect, name='dispatch')
class PublicAuthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AccountsThrottle]

    def validated(self, serializer_class, request):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


def token_user(uid):
    try:
        pk = urlsafe_base64_decode(uid).decode()
        return User.objects.select_for_update().get(pk=pk, is_active=True)
    except (ValueError, UnicodeError, DjangoValidationError, User.DoesNotExist, OverflowError):
        return None


def invalid_token(kind):
    return Response({'code': f'INVALID_{kind}_TOKEN',
                     'message': 'This link is invalid or expired. Request a new link.'}, status=400)


class VerifyEmailView(PublicAuthView):
    throttle_scope = 'verify'

    def post(self, request):
        data = self.validated(TokenSerializer, request)
        with transaction.atomic():
            user = token_user(data['uid'])
            if not email_verification_token.check_token(user, data['token']):
                return invalid_token('VERIFICATION')
            user.email_verified = True
            user.save(update_fields=['email_verified'])
        return Response({'message': 'Email verified'})


class ResendVerificationView(PublicAuthView):
    throttle_scope = 'resend'

    def post(self, request):
        data = self.validated(EmailSerializer, request)
        user = User.objects.filter(email=data['email'], is_active=True, email_verified=False).first()
        if user:
            send_verification_email(user)
        return Response({'message': 'If an account needs verification, a verification email has been sent.'})


class LoginView(PublicAuthView):
    throttle_scope = 'login'

    def post(self, request):
        data = self.validated(LoginSerializer, request)
        user = authenticate(request=request, email=data['email'], password=data['password'])
        if user is None:
            return Response({'code': 'AUTHENTICATION_REQUIRED', 'message': 'Invalid email or password.'}, status=401)
        if not user.email_verified:
            return Response({'code': 'EMAIL_NOT_VERIFIED', 'message': 'Verify your email before signing in.'}, status=403)
        login(request, user)
        return Response({'user': UserSerializer(user, context={'request': request}).data})


class PasswordResetView(PublicAuthView):
    throttle_scope = 'reset'

    def post(self, request):
        data = self.validated(EmailSerializer, request)
        user = User.objects.filter(email=data['email'], is_active=True).first()
        if user and user.has_usable_password():
            send_password_reset_email(user)
        return Response({'message': 'If an eligible account exists, a password reset email has been sent.'})


class PasswordResetConfirmView(PublicAuthView):
    throttle_scope = 'reset_confirm'

    def post(self, request):
        data = self.validated(ResetConfirmSerializer, request)
        with transaction.atomic():
            user = token_user(data['uid'])
            if not default_token_generator.check_token(user, data['token']):
                return invalid_token('RESET')
            try:
                validate_password(data['new_password'], user=user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'new_password': exc.messages})
            user.set_password(data['new_password'])
            user.save(update_fields=['password'])
        # Django rejects every existing session's previous password auth hash.
        return Response({'message': 'Password reset successful'})


@method_decorator(csrf_protect, name='dispatch')
class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]


class LogoutView(ProtectedView):
    def post(self, request):
        logout(request)
        return Response(status=204)


class MeView(ProtectedView):
    def get(self, request):
        return Response({'user': UserSerializer(request.user, context={'request': request}).data})

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise serializers.ValidationError({'username': ['This username is already taken.']})
        return self.get(request)


class PhotoView(ProtectedView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        serializer = PhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = serializer.validated_data['photo']
        suffix = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[photo.image_format]
        storage = request.user.profile_photo.storage
        new_name = None
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=request.user.pk)
                old_name = user.profile_photo.name
                user.profile_photo.save(f'{uuid4().hex}.{suffix}', photo, save=False)
                new_name = user.profile_photo.name
                user.save(update_fields=['profile_photo'])
                if old_name:
                    transaction.on_commit(lambda: storage.delete(old_name))
        except Exception:
            if new_name:
                storage.delete(new_name)
            raise
        return Response({'profile_photo_url': UserSerializer(user, context={'request': request}).data['profile_photo_url']})


class UserSearchView(ProtectedView):
    throttle_classes = [AccountsThrottle]
    throttle_scope = 'search'

    def get(self, request):
        if not request.user.email_verified:
            return Response({'code': 'EMAIL_NOT_VERIFIED', 'message': 'Verify your email before signing in.'}, status=403)
        query = request.query_params.get('username', '').strip().lower()
        if len(query) < 2:
            raise serializers.ValidationError({'username': ['Enter at least 2 characters.']})
        users = User.objects.filter(is_active=True, email_verified=True, username__istartswith=query).exclude(pk=request.user.pk).order_by('username', 'id').values('id', 'username', 'full_name')[:10]
        return Response({'results': list(users)})
