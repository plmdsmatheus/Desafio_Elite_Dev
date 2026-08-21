from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.events.serializers import EventSerializer

from .models import Reservation, Seat, Ticket
from .signing import sign_ticket_code

User = get_user_model()


class ReservationCreateSerializer(serializers.ModelSerializer):
    """Structural validation only (event published, quantity/seat_ids shape).
    Deliberately does NOT check seat availability — that's a locked,
    transactional check (see apps.ticketing.seating.hold_seats) that belongs
    in the view, not here, so it can return a 409 (stale selection) instead
    of DRF's blanket 400 for validation errors."""

    seat_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=False, write_only=True
    )

    class Meta:
        model = Reservation
        fields = ["event", "quantity", "seat_ids"]
        extra_kwargs = {"quantity": {"required": False}}

    def validate(self, attrs):
        event = attrs["event"]
        seat_ids = attrs.get("seat_ids")

        if event.status != event.Status.PUBLISHED:
            raise serializers.ValidationError({"event": "Este evento não está publicado."})

        if event.date_time <= timezone.now():
            raise serializers.ValidationError({"event": "Este evento já aconteceu."})

        if event.has_seat_map:
            if not seat_ids:
                raise serializers.ValidationError({"seat_ids": "Selecione ao menos um assento."})
            if len(seat_ids) != len(set(seat_ids)):
                raise serializers.ValidationError({"seat_ids": "Assentos duplicados na seleção."})
            attrs["quantity"] = len(seat_ids)
        else:
            quantity = attrs.get("quantity")
            if not quantity or quantity < 1:
                raise serializers.ValidationError(
                    {"quantity": "Precisa reservar pelo menos 1 ingresso."}
                )
            # "Courtesy" check for early feedback — not the source of truth. The
            # real guarantee against overselling happens atomically on payment
            # approval (see ReservationPayView). Seat-map events skip this
            # check entirely: their guarantee is the per-seat lock in
            # hold_seats, authoritative already at reservation time.
            if quantity > event.tickets_available:
                raise serializers.ValidationError(
                    {"quantity": f"Só restam {event.tickets_available} ingresso(s) disponível(is)."}
                )

        return attrs


class ReservationSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    seats = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = ["id", "event", "quantity", "status", "total_price", "created_at", "seats"]
        read_only_fields = fields

    def get_seats(self, obj) -> list[str]:
        return [seat.label for seat in obj.held_seats.all()]


class PaySerializer(serializers.Serializer):
    """Simulated payment — no sensitive data is actually persisted."""

    card_number = serializers.CharField(max_length=32)
    card_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    expiry = serializers.CharField(max_length=10, required=False, allow_blank=True)
    cvv = serializers.CharField(max_length=4, required=False, allow_blank=True)

    def validate_card_number(self, value):
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 4:
            raise serializers.ValidationError("Número de cartão inválido.")
        return digits


class TicketSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    qr_payload = serializers.SerializerMethodField()
    share_url = serializers.SerializerMethodField()
    seat_label = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "event",
            "public_code",
            "share_slug",
            "status",
            "used_at",
            "created_at",
            "qr_payload",
            "share_url",
            "seat_label",
        ]

    def get_qr_payload(self, obj) -> str:
        return sign_ticket_code(obj.public_code)

    def get_share_url(self, obj) -> str:
        return f"{settings.FRONTEND_BASE_URL}/t/{obj.share_slug}"

    def get_seat_label(self, obj) -> str | None:
        return obj.seat.label if obj.seat_id else None


class SeatSerializer(serializers.ModelSerializer):
    """Seat availability as seen by the requesting user — polled by the
    frontend while picking seats. `status` is "mine" only for the requester's
    own live hold, so their selection reads differently from everyone else's."""

    label = serializers.ReadOnlyField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Seat
        fields = ["id", "row_label", "number", "label", "status"]

    def get_status(self, obj) -> str:
        ticket = getattr(obj, "ticket", None)
        if ticket and ticket.status != Ticket.Status.CANCELED:
            return "sold"

        if (
            obj.reservation_id
            and obj.reservation.status == Reservation.Status.PENDING
            and obj.held_until
            and obj.held_until > timezone.now()
        ):
            user = self.context["request"].user
            if user.is_authenticated and obj.reservation.customer_id == user.id:
                return "mine"
            return "held"

        return "available"


class TicketTransferSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="E-mail de um cliente já cadastrado na plataforma.")

    def validate_email(self, value):
        requester = self.context["request"].user
        if value.strip().lower() == requester.email.lower():
            raise serializers.ValidationError("Você já é o dono deste ingresso.")

        recipient = User.objects.filter(email__iexact=value, role=User.Role.CUSTOMER).first()
        if recipient is None:
            raise serializers.ValidationError(
                "Não encontramos um cliente cadastrado com esse e-mail."
            )
        return recipient


class GateValidateSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="Payload assinado do QR ou o public_code digitado manualmente."
    )
    event_id = serializers.IntegerField(help_text="Evento selecionado na sessão da portaria.")


class PaymentResultSerializer(serializers.Serializer):
    """Documentation only — not used to build the actual response."""

    reservation = ReservationSerializer()
    payment_status = serializers.ChoiceField(choices=["approved", "declined"])
    tickets = TicketSerializer(many=True)


class GateValidateResultSerializer(serializers.Serializer):
    """Documentation only — not used to build the actual response."""

    result = serializers.ChoiceField(
        choices=["valido", "invalido", "ja_utilizado", "evento_errado"]
    )
    detail = serializers.CharField()
    ticket = TicketSerializer(required=False)
