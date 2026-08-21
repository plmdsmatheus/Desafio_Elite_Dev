import secrets
import uuid

from django.conf import settings
from django.db import models

from apps.events.models import Event

# Alphabet without ambiguous characters (no 0/O, 1/I/l) — meant for manual entry at the gate.
_PUBLIC_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def generate_public_code():
    return "".join(secrets.choice(_PUBLIC_CODE_ALPHABET) for _ in range(10))


# Module level (not nested in the classes) so drf-spectacular can import each
# choices via ENUM_NAME_OVERRIDES; the <Model>.Status aliases below keep the
# rest of the code reading naturally (Reservation.Status.PAID etc).
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


class Seat(models.Model):
    """A specific, non-fungible seat for events with assigned seating
    (`Event.has_seat_map`). `reservation` is the current holder: set the
    moment a customer picks the seat (not only once paid) so two customers
    can never both believe they hold the same seat — see ReservationCreateView.
    `held_until` bounds an unpaid hold; a hold past that timestamp is treated
    as free by every availability check even though the FK is only cleared
    lazily (on the next hold attempt, cancellation, or decline) — there's no
    background sweep, consistent with this project's "reserva pendente não
    trava estoque" stance for quantity-based reservations."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seats")
    row_label = models.CharField(max_length=4)
    number = models.PositiveIntegerField()

    reservation = models.ForeignKey(
        Reservation, null=True, blank=True, on_delete=models.SET_NULL, related_name="held_seats"
    )
    held_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["row_label", "number"]
        constraints = [
            models.UniqueConstraint(fields=["event", "row_label", "number"], name="unique_event_seat")
        ]

    def __str__(self):
        return f"{self.row_label}{self.number} — {self.event.title}"

    @property
    def label(self) -> str:
        return f"{self.row_label}{self.number}"


class Payment(models.Model):
    Status = PaymentStatus

    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="payment"
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    # Only the last digits of the simulated "card", to show on the receipt — never the full number.
    card_last_digits = models.CharField(max_length=4, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pagamento #{self.pk} — {self.status}"


class Ticket(models.Model):
    Status = TicketStatus

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="tickets")
    # Deliberately denormalized from reservation.event: the gate looks up by
    # ticket + event without an extra join to decide "wrong event".
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
        limit_choices_to={"role": "customer"},
    )
    # Only set for events with a seat map — general admission tickets have no seat.
    seat = models.OneToOneField(
        Seat, null=True, blank=True, on_delete=models.SET_NULL, related_name="ticket"
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
