from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer, IsGate
from apps.events.models import Event
from apps.events.serializers import EventSerializer

from .models import Payment, Reservation, Seat, Ticket
from .seating import (
    SeatsUnavailable,
    cancel_ticket_and_release_seat,
    hold_seats,
    release_reservation_hold,
    release_stale_holds_for_customer,
)
from .serializers import (
    GateValidateResultSerializer,
    GateValidateSerializer,
    PaySerializer,
    PaymentResultSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    SeatSerializer,
    TicketSerializer,
    TicketTransferSerializer,
)
from .sse import stream_while_changed
from .signing import unsign_ticket_code


@extend_schema_view(
    post=extend_schema(
        tags=["reservations"],
        summary="Reservar ingressos (quantidade)",
        responses=ReservationSerializer,
    )
)
class ReservationCreateView(generics.CreateAPIView):
    """For seat-map events, seat locking (and the Reservation save that goes
    with it) happens here rather than in the serializer, so a stale/taken
    seat selection can answer 409 instead of DRF's blanket 400 for validation
    errors — see apps.ticketing.seating.hold_seats."""

    permission_classes = [IsCustomer]
    serializer_class = ReservationCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.validated_data["event"]
        quantity = serializer.validated_data["quantity"]
        seat_ids = serializer.validated_data.get("seat_ids")

        reservation = Reservation(
            event=event,
            customer=request.user,
            quantity=quantity,
            total_price=event.price * quantity,
        )

        if event.has_seat_map:
            # Backing out of checkout without paying leaves the old
            # reservation dangling as PENDING with its seats still held —
            # release those first so a fresh pick (even of the very same
            # seat) never looks "taken" by the customer's own abandoned hold.
            release_stale_holds_for_customer(event, request.user)
            try:
                hold_seats(event, seat_ids, reservation)
            except SeatsUnavailable as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        else:
            reservation.save()

        return Response(
            ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED
        )


class ReservationReleaseView(APIView):
    """Lets the customer explicitly give up a still-unpaid reservation —
    "I changed my mind" / "I'm leaving this page" — freeing any held seats
    right away instead of making the next buyer wait out the 10-minute hold.
    The frontend fires this from a couple of places: an explicit "cancelar
    reserva" action, and a best-effort call when the checkout page unmounts
    with an unpaid reservation still open. Always answers 200 — silently a
    no-op if the reservation is no longer pending (already paid, declined, or
    already released) — since this is meant to be called fire-and-forget
    without the caller checking state first."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=["reservations"],
        summary="Desistir de uma reserva pendente (libera assentos na hora)",
        responses=ReservationSerializer,
    )
    def post(self, request, pk):
        with transaction.atomic():
            reservation = get_object_or_404(
                Reservation.objects.select_for_update(), pk=pk, customer=request.user
            )
            release_reservation_hold(reservation)

        return Response(ReservationSerializer(reservation).data)


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

            held_seats = []
            if event.has_seat_map:
                held_seats = list(Seat.objects.select_for_update().filter(reservation=reservation))
                if len(held_seats) != reservation.quantity:
                    # The 10-minute hold expired and (some of) the seats were
                    # picked up by someone else before this payment landed.
                    reservation.status = Reservation.Status.DECLINED
                    reservation.save(update_fields=["status", "updated_at"])
                    return Response(
                        {
                            "detail": "A reserva dos assentos expirou antes do pagamento. "
                            "Escolha os assentos novamente."
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            # The event may have been canceled after this reservation was
            # created but before payment landed — never issue a ticket for
            # that, even if the card would otherwise approve.
            if approved and event.status != Event.Status.PUBLISHED:
                approved = False

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
                if held_seats:
                    tickets = [
                        Ticket(reservation=reservation, event=event, owner=request.user, seat=seat)
                        for seat in held_seats
                    ]
                else:
                    tickets = [
                        Ticket(reservation=reservation, event=event, owner=request.user)
                        for _ in range(reservation.quantity)
                    ]
                Ticket.objects.bulk_create(tickets)
            elif held_seats:
                # Declined — release the holds immediately instead of making
                # someone else wait out the remainder of the 10-minute window.
                Seat.objects.filter(id__in=[seat.id for seat in held_seats]).update(
                    reservation=None, held_until=None
                )

        reservation.refresh_from_db()
        return Response(
            {
                "reservation": ReservationSerializer(reservation).data,
                "payment_status": payment.status,
                "tickets": TicketSerializer(tickets, many=True, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=["events"],
        summary="Mapa de assentos do evento",
        description="Só para eventos com has_seat_map=True. Sem paginação — o frontend faz "
        "polling deste endpoint a cada poucos segundos enquanto o cliente escolhe os assentos; "
        "a garantia real contra venda duplicada é o lock em hold_seats na criação da reserva, "
        "não esta leitura.",
    )
)
class EventSeatMapView(generics.ListAPIView):
    permission_classes = [IsCustomer]
    serializer_class = SeatSerializer
    pagination_class = None

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        return event.seats.select_related("ticket", "reservation")


def _sse_response(snapshot):
    response = StreamingHttpResponse(
        stream_while_changed(snapshot), content_type="text/event-stream"
    )
    # Standard SSE headers: no-cache so an intermediary never serves a stale
    # snapshot from cache, and X-Accel-Buffering so an nginx-style proxy in
    # front of the app (as on Render) doesn't buffer the stream into one big
    # delayed chunk instead of forwarding it live.
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@extend_schema_view(
    get=extend_schema(
        tags=["events"],
        summary="Contagem de ingressos disponíveis em tempo real (SSE)",
        description="Server-Sent Events — só emite um evento novo quando "
        "tickets_available muda. Pensado pra eventos sem mapa de assentos "
        "(com mapa, a disponibilidade já é visual, assento por assento).",
    )
)
class EventAvailabilityStreamView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request, event_id):
        get_object_or_404(Event, pk=event_id)

        def snapshot():
            event = get_object_or_404(Event, pk=event_id)
            return {
                "tickets_available": event.tickets_available,
                "tickets_sold": event.tickets_sold,
                "capacity": event.capacity,
            }

        return _sse_response(snapshot)


@extend_schema_view(
    get=extend_schema(
        tags=["events"],
        summary="Mapa de assentos em tempo real (SSE)",
        description="Substitui o polling do frontend: emite o mapa de assentos completo "
        "sempre que algum assento muda de estado. A garantia real contra venda duplicada "
        "continua sendo o lock em hold_seats na criação da reserva, não esta leitura.",
    )
)
class EventSeatMapStreamView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request, event_id):
        get_object_or_404(Event, pk=event_id)

        def snapshot():
            event = get_object_or_404(Event, pk=event_id)
            seats = event.seats.select_related("ticket", "reservation")
            return SeatSerializer(seats, many=True, context={"request": request}).data

        return _sse_response(snapshot)


@extend_schema_view(get=extend_schema(tags=["tickets"], summary="Meus ingressos"))
class MyTicketsView(generics.ListAPIView):
    """Valid tickets sort first (then used, then canceled) so a still-usable
    ticket never gets buried on page 2 behind older canceled/used ones — the
    page size doesn't know about status, so status has to drive the order."""

    permission_classes = [IsCustomer]
    serializer_class = TicketSerializer

    def get_queryset(self):
        status_rank = Case(
            When(status=Ticket.Status.VALID, then=Value(0)),
            When(status=Ticket.Status.USED, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
        return (
            Ticket.objects.filter(owner=self.request.user)
            .select_related("event")
            .annotate(_status_rank=status_rank)
            .order_by("_status_rank", "-created_at")
        )


class TicketCancelView(APIView):
    """Cancels a single ticket and returns it to stock. Event.tickets_sold is
    derived live from non-canceled Ticket rows (see Event.with_sold_counts),
    so flipping the status here is the entire "return to stock" — no separate
    counter to reconcile. If the ticket is tied to a seat hold (seat maps),
    the seat is released in the same transaction so it becomes selectable
    again immediately."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=["tickets"],
        summary="Cancelar ingresso (devolve ao estoque)",
        responses=TicketSerializer,
    )
    def post(self, request, pk):
        with transaction.atomic():
            ticket = get_object_or_404(
                # `of=("self",)`: FOR UPDATE can't apply across the LEFT OUTER
                # JOIN to the nullable `seat` relation — restrict the lock to
                # the ticket row itself.
                Ticket.objects.select_for_update(of=("self",)).select_related("seat"),
                pk=pk,
                owner=request.user,
            )

            if ticket.status != Ticket.Status.VALID:
                return Response(
                    {"detail": "Só é possível cancelar ingressos válidos."},
                    status=status.HTTP_409_CONFLICT,
                )

            if ticket.event.date_time <= timezone.now():
                return Response(
                    {"detail": "Não é possível cancelar o ingresso de um evento que já aconteceu."},
                    status=status.HTTP_409_CONFLICT,
                )

            cancel_ticket_and_release_seat(ticket)

        return Response(TicketSerializer(ticket, context={"request": request}).data)


class TicketTransferView(APIView):
    """Reassigns a ticket to another customer already registered on the site.
    Only the current owner can transfer it, and only while it's still valid —
    once used/canceled, ownership no longer matters for the gate."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=["tickets"],
        summary="Enviar ingresso para outro cliente cadastrado",
        request=TicketTransferSerializer,
        responses=TicketSerializer,
    )
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, owner=request.user)

        if ticket.status != Ticket.Status.VALID:
            return Response(
                {"detail": "Só é possível transferir ingressos válidos."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = TicketTransferSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        recipient = serializer.validated_data["email"]

        ticket.owner = recipient
        ticket.save(update_fields=["owner"])

        return Response(TicketSerializer(ticket, context={"request": request}).data)


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
