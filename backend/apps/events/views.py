from django.db.models import Q
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizer

from .models import Event
from .serializers import EventSerializer, EventWriteSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["events"],
        summary="Buscar eventos publicados",
        parameters=[
            OpenApiParameter("q", str, required=False, description="Busca em título/local."),
            OpenApiParameter("city", str, required=False, description="Filtra por cidade."),
            OpenApiParameter(
                "category", str, required=False, enum=["show", "movie"], description="Filtra por categoria."
            ),
            OpenApiParameter("date", str, required=False, description="Filtra por data (YYYY-MM-DD)."),
        ],
    ),
    post=extend_schema(tags=["events"], summary="Criar evento (organizador)"),
)
class EventListCreateView(generics.ListCreateAPIView):
    """Public GET (search/filter over published events) + organizer POST."""

    def get_serializer_class(self):
        return EventWriteSerializer if self.request.method == "POST" else EventSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOrganizer()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Event.objects.with_sold_counts().filter(status=Event.Status.PUBLISHED)
        params = self.request.query_params

        q = params.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(venue_name__icontains=q))

        city = params.get("city")
        if city:
            qs = qs.filter(city__icontains=city)

        category = params.get("category")
        if category:
            qs = qs.filter(category=category)

        date = params.get("date")
        if date:
            parsed = parse_date(date)
            if parsed:
                qs = qs.filter(date_time__date=parsed)

        return qs

    def perform_create(self, serializer):
        event = serializer.save(organizer=self.request.user)
        if event.has_seat_map:
            # Local import: apps.events must not depend on apps.ticketing at
            # module load time (see Event.tickets_sold for the same reason).
            from apps.ticketing.seating import generate_seats_for_event

            generate_seats_for_event(event)

    def create(self, request, *args, **kwargs):
        # EventWriteSerializer doesn't expose id/tickets_sold/etc — use the read
        # serializer for the response so it returns the full created event.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = EventSerializer(serializer.instance)
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["events"], summary="Detalhe do evento"),
    put=extend_schema(tags=["events"], summary="Substituir evento (organizador dono)"),
    patch=extend_schema(tags=["events"], summary="Editar evento (organizador dono)"),
)
class EventDetailView(generics.RetrieveUpdateAPIView):
    """Public GET (published event, or a draft if it's the owning organizer) +
    PATCH/PUT restricted to the owning organizer."""

    def get_serializer_class(self):
        return EventWriteSerializer if self.request.method in ("PUT", "PATCH") else EventSerializer

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsOrganizer()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        if self.request.method in ("PUT", "PATCH"):
            # Scoping to the owner here already handles object-level permission:
            # a non-owner gets a 404, no need for a separate ownership check.
            return Event.objects.filter(organizer=self.request.user)

        user = self.request.user
        qs = Event.objects.with_sold_counts()
        if user.is_authenticated and getattr(user, "is_organizer", False):
            return qs.filter(Q(status=Event.Status.PUBLISHED) | Q(organizer=user))
        return qs.filter(status=Event.Status.PUBLISHED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if serializer.instance.has_seat_map:
            from apps.ticketing.seating import generate_seats_for_event

            generate_seats_for_event(serializer.instance)

        if serializer.instance.status == Event.Status.CANCELED:
            # Canceling the event must invalidate its tickets too — otherwise
            # a customer could still present a "valid" ticket at the gate (or
            # transfer/cancel it) for an event that isn't happening anymore.
            # Idempotent: a no-op on a second save once already canceled,
            # since every valid ticket was already flipped the first time.
            from apps.ticketing.models import Ticket, TicketStatus

            Ticket.objects.filter(event=serializer.instance, status=TicketStatus.VALID).update(
                status=TicketStatus.CANCELED
            )

        return Response(EventSerializer(serializer.instance).data)


@extend_schema_view(
    get=extend_schema(tags=["events"], summary="Meus eventos (organizador, todos os status)")
)
class OrganizerEventListView(generics.ListAPIView):
    """Organizer's own listing (every status, with sold/capacity)."""

    permission_classes = [IsOrganizer]
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.with_sold_counts().filter(organizer=self.request.user)
