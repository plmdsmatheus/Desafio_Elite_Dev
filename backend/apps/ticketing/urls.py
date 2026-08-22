from django.urls import path

from .views import (
    EventAvailabilityStreamView,
    EventSeatMapStreamView,
    EventSeatMapView,
    GateEventListView,
    GateValidateView,
    MyTicketsView,
    PublicTicketView,
    ReservationCreateView,
    ReservationPayView,
    ReservationReleaseView,
    TicketCancelView,
    TicketTransferView,
)

app_name = "ticketing"

urlpatterns = [
    path("reservations", ReservationCreateView.as_view(), name="reservation-create"),
    path("reservations/<int:pk>/pay", ReservationPayView.as_view(), name="reservation-pay"),
    path("reservations/<int:pk>/release", ReservationReleaseView.as_view(), name="reservation-release"),
    path("events/<int:event_id>/seats", EventSeatMapView.as_view(), name="event-seats"),
    path(
        "events/<int:event_id>/seats/stream",
        EventSeatMapStreamView.as_view(),
        name="event-seats-stream",
    ),
    path(
        "events/<int:event_id>/availability/stream",
        EventAvailabilityStreamView.as_view(),
        name="event-availability-stream",
    ),
    path("tickets/mine", MyTicketsView.as_view(), name="tickets-mine"),
    path("tickets/<int:pk>/transfer", TicketTransferView.as_view(), name="ticket-transfer"),
    path("tickets/<int:pk>/cancel", TicketCancelView.as_view(), name="ticket-cancel"),
    path("tickets/<uuid:share_slug>/public", PublicTicketView.as_view(), name="ticket-public"),
    path("gate/events", GateEventListView.as_view(), name="gate-events"),
    path("gate/validate", GateValidateView.as_view(), name="gate-validate"),
]
