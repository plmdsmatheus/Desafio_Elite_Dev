from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer, IsGate
from apps.events.models import Event
from apps.events.serializers import EventSerializer

from .models import Payment, Reservation, Ticket
from .serializers import (
    GateValidateResultSerializer,
    GateValidateSerializer,
    PaySerializer,
    PaymentResultSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    TicketSerializer,
)
from .signing import unsign_ticket_code


@extend_schema_view(
    post=extend_schema(
        tags=["reservations"],
        summary="Reservar ingressos (quantidade)",
        responses=ReservationSerializer,
    )
)
class ReservationCreateView(generics.CreateAPIView):
    permission_classes = [IsCustomer]
    serializer_class = ReservationCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reservation = serializer.save()
        return Response(
            ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED
        )


class ReservationPayView(APIView):
    """Simula o pagamento. A checagem final de capacidade acontece AQUI — não na
    criação da reserva — dentro de uma transação com lock no Event. É esse lock
    que garante que o mesmo lugar não seja vendido duas vezes sob concorrência."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=["reservations"],
        summary="Pagar reserva (simulado)",
        description="Cartão terminado em '0000' é sempre recusado; qualquer outro número aprova "
        "(sujeito a ainda haver capacidade disponível no evento, checado sob lock).",
        request=PaySerializer,
        responses=PaymentResultSerializer,
    )
    def post(self, request, pk):
        reservation = get_object_or_404(
            Reservation,
            pk=pk,
            customer=request.user,
            status=Reservation.Status.PENDING,
        )

        pay_serializer = PaySerializer(data=request.data)
        pay_serializer.is_valid(raise_exception=True)
        card_number = pay_serializer.validated_data["card_number"]

        # Regra determinística e documentada no README: cartão terminado em
        # "0000" é sempre recusado, qualquer outro é aprovado.
        approved = not card_number.endswith("0000")

        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=reservation.event_id)

            if approved and event.tickets_sold + reservation.quantity > event.capacity:
                approved = False

            payment = Payment.objects.create(
                reservation=reservation,
                status=Payment.Status.APPROVED if approved else Payment.Status.DECLINED,
                card_last_digits=card_number[-4:],
            )

            reservation.status = (
                Reservation.Status.PAID if approved else Reservation.Status.DECLINED
            )
            reservation.save(update_fields=["status", "updated_at"])

            tickets = []
            if approved:
                tickets = [
                    Ticket(reservation=reservation, event=event, owner=request.user)
                    for _ in range(reservation.quantity)
                ]
                Ticket.objects.bulk_create(tickets)

        reservation.refresh_from_db()
        return Response(
            {
                "reservation": ReservationSerializer(reservation).data,
                "payment_status": payment.status,
                "tickets": TicketSerializer(tickets, many=True, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(get=extend_schema(tags=["tickets"], summary="Meus ingressos"))
class MyTicketsView(generics.ListAPIView):
    permission_classes = [IsCustomer]
    serializer_class = TicketSerializer

    def get_queryset(self):
        return Ticket.objects.filter(owner=self.request.user).select_related("event")


@extend_schema_view(
    get=extend_schema(
        tags=["tickets"], summary="Ver ingresso compartilhado (link público, sem login)"
    )
)
class PublicTicketView(generics.RetrieveAPIView):
    """Link compartilhável — o UUID do share_slug já é a proteção, sem exigir login."""

    permission_classes = [permissions.AllowAny]
    serializer_class = TicketSerializer
    lookup_field = "share_slug"
    lookup_url_kwarg = "share_slug"
    queryset = Ticket.objects.select_related("event")


@extend_schema_view(
    get=extend_schema(tags=["gate"], summary="Eventos publicados (sessões para validação)")
)
class GateEventListView(generics.ListAPIView):
    """Eventos publicados, pra portaria escolher a sessão de validação."""

    permission_classes = [IsGate]
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.filter(status=Event.Status.PUBLISHED)


class GateValidateView(APIView):
    """Sempre responde 200 com um `result` entre valido/invalido/ja_utilizado/
    evento_errado — o front decide o que mostrar sem precisar inspecionar status
    HTTP além dos erros de validação de entrada (400)."""

    permission_classes = [IsGate]

    @extend_schema(
        tags=["gate"],
        summary="Validar ingresso na portaria",
        description="Aceita tanto o payload assinado do QR quanto o public_code digitado à mão.",
        request=GateValidateSerializer,
        responses=GateValidateResultSerializer,
    )
    def post(self, request):
        serializer = GateValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_code = serializer.validated_data["code"].strip()
        event_id = serializer.validated_data["event_id"]

        # Aceita tanto o payload assinado do QR quanto o public_code digitado à mão.
        public_code = unsign_ticket_code(raw_code) or raw_code

        with transaction.atomic():
            ticket = (
                Ticket.objects.select_for_update()
                .select_related("event")
                .filter(public_code=public_code)
                .first()
            )

            if ticket is None or ticket.status == Ticket.Status.CANCELED:
                return Response({"result": "invalido", "detail": "Ingresso não encontrado."})

            if ticket.event_id != event_id:
                return Response(
                    {
                        "result": "evento_errado",
                        "detail": f"Este ingresso é de outro evento: {ticket.event.title}.",
                    }
                )

            if ticket.status == Ticket.Status.USED:
                return Response(
                    {
                        "result": "ja_utilizado",
                        "detail": f"Ingresso já validado em {ticket.used_at:%d/%m/%Y %H:%M}.",
                    }
                )

            ticket.status = Ticket.Status.USED
            ticket.used_at = timezone.now()
            ticket.save(update_fields=["status", "used_at"])

        return Response(
            {
                "result": "valido",
                "detail": "Ingresso validado com sucesso.",
                "ticket": TicketSerializer(ticket, context={"request": request}).data,
            }
        )
