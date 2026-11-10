
import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .managers import UserManager


username_validator = RegexValidator(
    regex=r"^[a-z][a-z0-9_]{2,29}$",
    message=(
        "Username must start with a lowercase letter "
        "and contain 3 to 30 lowercase letters, "
        "numbers, or underscores."
    ),
)

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    email = models.EmailField(unique=True)

    username = models.CharField(
        max_length=30,
        unique=True,
        validators=[username_validator],
    )

    full_name = models.CharField(max_length=100)

    upi_id = models.CharField(
        max_length=100,
        blank=True,
    )

    profile_photo = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True,
    )

    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "full_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="unique_user_email_lower",
            ),
            models.UniqueConstraint(
                Lower("username"),
                name="unique_user_username_lower",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()

        if self.username:
            self.username = self.username.strip().lower()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

