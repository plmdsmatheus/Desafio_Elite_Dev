from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
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
            raise ValueError("Superuser precisa ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa ter is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Usuário único com três papéis mutuamente exclusivos.

    Cadastro público (API) só cria clientes; organizador e portaria são
    provisionados via seed/admin, por serem contas operacionais.
    """

    class Role(models.TextChoices):
        ORGANIZER = "organizer", "Organizador"
        CUSTOMER = "customer", "Cliente"
        GATE = "gate", "Portaria"

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
