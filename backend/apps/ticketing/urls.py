from django.urls import path

from .views import (
    GateEventListView,
    GateValidateView,
    MyTicketsView,
    PublicTicketView,
    ReservationCreateView,
    ReservationPayView,
    TicketTransferView,
)

app_name = "ticketing"

urlpatterns = [
    path("reservations", ReservationCreateView.as_view(), name="reservation-create"),
    path("reservations/<int:pk>/pay", ReservationPayView.as_view(), name="reservation-pay"),
    path("tickets/mine", MyTicketsView.as_view(), name="tickets-mine"),
    path("tickets/<int:pk>/transfer", TicketTransferView.as_view(), name="ticket-transfer"),
    path("tickets/<uuid:share_slug>/public", PublicTicketView.as_view(), name="ticket-public"),
    path("gate/events", GateEventListView.as_view(), name="gate-events"),
    path("gate/validate", GateValidateView.as_view(), name="gate-validate"),
]
