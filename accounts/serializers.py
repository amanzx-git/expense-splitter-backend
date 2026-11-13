
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,29}$")
UPI_PATTERN = re.compile(
    r"^[A-Za-z0-9._-]{2,64}@[A-Za-z0-9.-]{2,35}$"
)


class UserSerializer(serializers.ModelSerializer):
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "full_name",
            "email",
            "email_verified",
            "upi_id",
            "profile_photo_url",
        )
        read_only_fields = fields

    def get_profile_photo_url(self, obj):
        if not obj.profile_photo:
            return None

        request = self.context.get("request")
        if request is None:
            return None

        return request.build_absolute_uri(obj.profile_photo.url)


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30)
    full_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    confirm_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    upi_id = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
    )

    def validate_username(self, value):
        value = value.strip().lower()

        if not USERNAME_PATTERN.fullmatch(value):
            raise serializers.ValidationError(
                "Username must start with a lowercase letter "
                "and contain 3 to 30 letters, digits or underscores."
            )

        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )

        return value

    def validate_full_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Full name cannot be empty."
            )

        return value

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    def validate_upi_id(self, value):
        value = value.strip()

        if value and not UPI_PATTERN.fullmatch(value):
            raise serializers.ValidationError(
                "Enter a valid UPI ID."
            )

        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": ["Passwords do not match."]
            })

        candidate_user = User(
            email=attrs["email"],
            username=attrs["username"],
            full_name=attrs["full_name"],
        )

        try:
            validate_password(
                attrs["password"],
                user=candidate_user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({
                "password": exc.messages
            })

        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")

        return User.objects.create_user(
            password=password,
            **validated_data,
        )
    
    
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown_fields = set(data) - set(self.fields)

            if unknown_fields:
                raise serializers.ValidationError({
                    field: ["This field is not allowed."]
                    for field in sorted(unknown_fields)
                })

        return super().to_internal_value(data)    
        


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if hasattr(data, 'keys'):
            unknown = set(data.keys()) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: ['This field is not allowed.'] for key in sorted(unknown)})
        return super().to_internal_value(data)


class EmailSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.lower()


class LoginSerializer(EmailSerializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class TokenSerializer(StrictSerializer):
    uid = serializers.CharField(max_length=200)
    token = serializers.CharField(max_length=200)


class ResetConfirmSerializer(TokenSerializer):
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)
    confirm_password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': ['Passwords do not match.']})
        return attrs


class ProfileSerializer(StrictSerializer):
    username = serializers.CharField(max_length=30, required=False)
    full_name = serializers.CharField(max_length=100, required=False)
    upi_id = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_username(self, value):
        value = value.lower()
        if not USERNAME_PATTERN.fullmatch(value):
            raise serializers.ValidationError('Enter a valid username.')
        if User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    validate_upi_id = RegistrationSerializer.validate_upi_id

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save(update_fields=list(validated_data))
        return instance


class PhotoSerializer(StrictSerializer):
    photo = serializers.ImageField()

    def validate_photo(self, value):
        import warnings
        from PIL import Image
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError('Photo must be at most 2 MiB.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(value) as image:
                    if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                        raise ValueError('Unsupported image format')
                    image.verify()
                value.seek(0)
                with Image.open(value) as image:
                    image.load()
                    value.image_format = image.format
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise serializers.ValidationError('Upload a valid JPG, PNG or WebP image.')
        finally:
            value.seek(0)
        return value
