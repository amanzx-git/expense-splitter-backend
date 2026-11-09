
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")

        email = self.normalize_email(email).strip().lower()

        username = extra_fields.get("username")
        if not username:
            raise ValueError("Users must have a username.")

        extra_fields["username"] = username.strip().lower()

        user = self.model(email=email, **extra_fields)

        # Hash and assign the password BEFORE validation.
        user.set_password(password)

        # Validate fields and uniqueness.
        user.full_clean()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("email_verified", True)

        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
