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
    """Simulates the payment. The final capacity check happens HERE — not when
    the reservation is created — inside a transaction that locks the Event.
    That lock is what guarantees the same seat isn't sold twice under
    concurrency."""

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
        pay_serializer = PaySerializer(data=request.data)
        pay_serializer.is_valid(raise_exception=True)
        card_number = pay_serializer.validated_data["card_number"]

        # Deterministic rule, documented in the README: a card ending in "0000"
        # is always declined, any other number is approved.
        approved = not card_number.endswith("0000")

        with transaction.atomic():
            # Lock the reservation itself: without this, a duplicate POST for the
            # same payment (double click, network retry) lets both requests pass
            # the status check, and the second one hits the unique constraint on
            # Payment.reservation.
            reservation = get_object_or_404(
                Reservation.objects.select_for_update(), pk=pk, customer=request.user
            )
            if reservation.status != Reservation.Status.PENDING:
                return Response(
                    {"detail": "Esta reserva não está mais pendente de pagamento."},
                    status=status.HTTP_409_CONFLICT,
                )

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
    """Shareable link — the share_slug UUID is itself the protection, no login required."""

    permission_classes = [permissions.AllowAny]
    serializer_class = TicketSerializer
    lookup_field = "share_slug"
    lookup_url_kwarg = "share_slug"
    queryset = Ticket.objects.select_related("event")


@extend_schema_view(
    get=extend_schema(tags=["gate"], summary="Eventos publicados (sessões para validação)")
)
class GateEventListView(generics.ListAPIView):
    """Published events, for the gate to pick which validation session it's running."""

    permission_classes = [IsGate]
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.with_sold_counts().filter(status=Event.Status.PUBLISHED)


class GateValidateView(APIView):
    """Always answers 200 with a `result` among valido/invalido/ja_utilizado/
    evento_errado — the frontend decides what to show without needing to
    inspect the HTTP status beyond input validation errors (400)."""

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

        # Accepts either the signed QR payload or the manually typed public_code.
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
