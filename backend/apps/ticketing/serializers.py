from django.conf import settings
from rest_framework import serializers

from apps.events.serializers import EventSerializer

from .models import Reservation, Ticket
from .signing import sign_ticket_code


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

        # Checagem "de cortesia" pra dar feedback cedo — não é a fonte da verdade.
        # A garantia real de não vender a mesma vaga duas vezes acontece de forma
        # atômica na aprovação do pagamento (ver ReservationPayView).
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
    """Pagamento simulado — nenhum dado sensível é persistido de verdade."""

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


class GateValidateSerializer(serializers.Serializer):
    code = serializers.CharField(
        help_text="Payload assinado do QR ou o public_code digitado manualmente."
    )
    event_id = serializers.IntegerField(help_text="Evento selecionado na sessão da portaria.")


class PaymentResultSerializer(serializers.Serializer):
    """Só para documentação — não é usado para montar a resposta de verdade."""

    reservation = ReservationSerializer()
    payment_status = serializers.ChoiceField(choices=["approved", "declined"])
    tickets = TicketSerializer(many=True)


class GateValidateResultSerializer(serializers.Serializer):
    """Só para documentação — não é usado para montar a resposta de verdade."""

    result = serializers.ChoiceField(
        choices=["valido", "invalido", "ja_utilizado", "evento_errado"]
    )
    detail = serializers.CharField()
    ticket = TicketSerializer(required=False)
