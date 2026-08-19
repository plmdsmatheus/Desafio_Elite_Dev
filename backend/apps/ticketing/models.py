import secrets
import uuid

from django.conf import settings
from django.db import models

from apps.events.models import Event

# Alfabeto sem caracteres ambíguos (sem 0/O, 1/I/l) — pensado pra digitação manual na portaria.
_PUBLIC_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def generate_public_code():
    return "".join(secrets.choice(_PUBLIC_CODE_ALPHABET) for _ in range(10))


# Nível de módulo (não aninhadas na classe) pra o drf-spectacular conseguir
# importar cada choices via ENUM_NAME_OVERRIDES; os aliases <Model>.Status
# abaixo preservam a leitura no resto do código (Reservation.Status.PAID etc).
class ReservationStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    PAID = "paid", "Pago"
    DECLINED = "declined", "Recusado"
    CANCELED = "canceled", "Cancelado"


class PaymentStatus(models.TextChoices):
    APPROVED = "approved", "Aprovado"
    DECLINED = "declined", "Recusado"


class TicketStatus(models.TextChoices):
    VALID = "valid", "Válido"
    USED = "used", "Utilizado"
    CANCELED = "canceled", "Cancelado"


class Reservation(models.Model):
    Status = ReservationStatus

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reservations")
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
        limit_choices_to={"role": "customer"},
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reserva #{self.pk} — {self.event.title} x{self.quantity} ({self.status})"


class Payment(models.Model):
    Status = PaymentStatus

    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="payment"
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    # Só os últimos dígitos do "cartão" simulado, pra exibir no recibo — nunca o número completo.
    card_last_digits = models.CharField(max_length=4, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pagamento #{self.pk} — {self.status}"


class Ticket(models.Model):
    Status = TicketStatus

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="tickets")
    # Denormalizado a partir de reservation.event de propósito: a portaria consulta por
    # ticket + evento sem precisar de join extra pra decidir "evento errado".
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
        limit_choices_to={"role": "customer"},
    )

    public_code = models.CharField(
        max_length=10, unique=True, default=generate_public_code, editable=False
    )
    share_slug = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Ticket {self.public_code} — {self.event.title} ({self.status})"
