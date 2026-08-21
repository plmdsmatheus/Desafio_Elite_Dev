from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


# Module level (not nested in the class) so drf-spectacular can import it via
# ENUM_NAME_OVERRIDES; the User.Role alias below keeps the rest of the code
# reading naturally (User.Role.CUSTOMER etc).
class UserRole(models.TextChoices):
    ORGANIZER = "organizer", "Organizador"
    CUSTOMER = "customer", "Cliente"
    GATE = "gate", "Portaria"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.CUSTOMER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ORGANIZER)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Single user model with three mutually exclusive roles.

    Public signup (API) always creates a customer; organizer and gate accounts
    are provisioned via seed/admin, since those are operational accounts.
    """

    Role = UserRole

    username = None
    email = models.EmailField("e-mail", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    @property
    def is_organizer(self):
        return self.role == self.Role.ORGANIZER

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_gate(self):
        return self.role == self.Role.GATE
