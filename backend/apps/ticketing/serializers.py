from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.events.serializers import EventSerializer

from .models import Reservation, Ticket
from .signing import sign_ticket_code

User = get_user_model()


class ReservationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = ["event", "quantity"]

    def validate(self, attrs):
        event = attrs["event"]
        quantity = attrs["quantity"]

        if quantity < 1:
            raise serializers.ValidationError(
                {"quantity": "Precisa reservar pelo menos 1 ingresso."}
            )

        if event.status != event.Status.PUBLISHED:
            raise serializers.ValidationError({"event": "Este evento não está publicado."})

        # "Courtesy" check for early feedback — not the source of truth. The real
        # guarantee against overselling happens atomically on payment approval
        # (see ReservationPayView).
        if quantity > event.tickets_available:
            raise serializers.ValidationError(
                {"quantity": f"Só restam {event.tickets_available} ingresso(s) disponível(is)."}
            )

        return attrs

    def create(self, validated_data):
        event = validated_data["event"]
        quantity = validated_data["quantity"]
        customer = self.context["request"].user
        return Reservation.objects.create(
            event=event,
            customer=customer,
            quantity=quantity,
            total_price=event.price * quantity,
        )


class ReservationSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = ["id", "event", "quantity", "status", "total_price", "created_at"]
        read_only_fields = fields


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
        ]

    def get_qr_payload(self, obj) -> str:
        return sign_ticket_code(obj.public_code)

    def get_share_url(self, obj) -> str:
        return f"{settings.FRONTEND_BASE_URL}/t/{obj.share_slug}"


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
