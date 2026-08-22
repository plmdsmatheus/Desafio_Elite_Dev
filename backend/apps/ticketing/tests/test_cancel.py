import pytest

from apps.events.models import Event
from apps.ticketing.models import Ticket


@pytest.mark.django_db
class TestTicketCancel:
    def _issue_ticket(self, api_client, customer, event):
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": event.id, "quantity": 1}, format="json"
        ).data["id"]
        pay_response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        return pay_response.data["tickets"][0]["id"]

    def test_owner_can_cancel_and_stock_is_returned(self, api_client, customer, published_event):
        ticket_id = self._issue_ticket(api_client, customer, published_event)

        available_before = Event.objects.get(pk=published_event.id).tickets_available

        response = api_client.post(f"/api/tickets/{ticket_id}/cancel")

        assert response.status_code == 200, response.data
        assert response.data["status"] == "canceled"

        event = Event.objects.get(pk=published_event.id)
        assert event.tickets_available == available_before + 1

    def test_canceled_ticket_moves_out_of_mine_valid_list(
        self, api_client, customer, published_event
    ):
        ticket_id = self._issue_ticket(api_client, customer, published_event)
        api_client.post(f"/api/tickets/{ticket_id}/cancel")

        mine = api_client.get("/api/tickets/mine").data
        canceled = next(t for t in mine["results"] if t["id"] == ticket_id)
        assert canceled["status"] == "canceled"

    def test_cannot_cancel_someone_elses_ticket(
        self, api_client, customer, customer2, published_event
    ):
        ticket_id = self._issue_ticket(api_client, customer, published_event)

        api_client.force_authenticate(user=customer2)
        response = api_client.post(f"/api/tickets/{ticket_id}/cancel")
        assert response.status_code == 404

    def test_cannot_cancel_twice(self, api_client, customer, published_event):
        ticket_id = self._issue_ticket(api_client, customer, published_event)

        api_client.post(f"/api/tickets/{ticket_id}/cancel")
        response = api_client.post(f"/api/tickets/{ticket_id}/cancel")
        assert response.status_code == 409

    def test_cannot_cancel_a_used_ticket(self, api_client, customer, published_event, gate_user):
        ticket_id = self._issue_ticket(api_client, customer, published_event)
        ticket = Ticket.objects.get(pk=ticket_id)

        api_client.force_authenticate(user=gate_user)
        api_client.post(
            "/api/gate/validate",
            {"code": ticket.public_code, "event_id": published_event.id},
            format="json",
        )

        api_client.force_authenticate(user=customer)
        response = api_client.post(f"/api/tickets/{ticket_id}/cancel")
        assert response.status_code == 409

    def test_cannot_cancel_ticket_for_past_event(self, api_client, customer, published_event):
        from django.utils import timezone
        from datetime import timedelta

        ticket_id = self._issue_ticket(api_client, customer, published_event)

        published_event.date_time = timezone.now() - timedelta(days=1)
        published_event.save()

        response = api_client.post(f"/api/tickets/{ticket_id}/cancel")
        assert response.status_code == 409

    def test_valid_ticket_isnt_buried_on_page_2_by_older_canceled_ones(
        self, api_client, customer, published_event
    ):
        """Reported in practice: buy 7 tickets, cancel 6 — with a fixed page
        size (6) and only -created_at as ordering, the one still-valid ticket
        can land on page 2 since it isn't necessarily the newest of the 7.
        Valid tickets must sort before used/canceled ones."""
        published_event.capacity = 7
        published_event.save()

        ticket_ids = [self._issue_ticket(api_client, customer, published_event) for _ in range(7)]
        for ticket_id in ticket_ids[:6]:
            response = api_client.post(f"/api/tickets/{ticket_id}/cancel")
            assert response.status_code == 200, response.data

        response = api_client.get("/api/tickets/mine")
        assert response.status_code == 200
        first_page_ids = [t["id"] for t in response.data["results"]]
        assert ticket_ids[6] in first_page_ids
        assert response.data["results"][0]["id"] == ticket_ids[6]
        assert response.data["results"][0]["status"] == "valid"

    def test_a_canceled_ticket_frees_the_spot_for_a_new_purchase(
        self, api_client, customer, customer2, published_event
    ):
        """Regression guard for the tickets_sold refactor: capacity is now
        derived from live (non-canceled) Ticket rows instead of the paid
        reservation's fixed quantity, specifically so a cancellation is
        immediately purchasable by someone else."""
        published_event.capacity = 1
        published_event.save()

        ticket_id = self._issue_ticket(api_client, customer, published_event)
        api_client.post(f"/api/tickets/{ticket_id}/cancel")

        api_client.force_authenticate(user=customer2)
        reservation_id = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 1}, format="json"
        ).data["id"]
        response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        assert response.data["payment_status"] == "approved"


@pytest.mark.django_db
class TestCancelSeatTicketRegression:
    """Bug reported in practice: buy N seat tickets, cancel all of them, then
    try to buy those same seats again — some looked unselectable, and the
    rest crashed the payment with a Postgres UniqueViolation on
    ticketing_ticket_seat_id_key. Root cause: `Ticket.seat` is a
    OneToOneField (a DB-level unique column) — canceling a ticket flipped its
    status but never cleared the `seat` FK, so the canceled ticket's row
    permanently occupied that seat's one-and-only unique slot. A later
    ticket for the same seat could never be inserted."""

    def _seat_ids(self, event, labels):
        from apps.ticketing.models import Seat

        seats = {s.label: s.id for s in Seat.objects.filter(event=event)}
        return [seats[label] for label in labels]

    def _buy_seats(self, api_client, customer, event, labels):
        api_client.force_authenticate(user=customer)
        seat_ids = self._seat_ids(event, labels)
        reservation_id = api_client.post(
            "/api/reservations", {"event": event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]
        pay_response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        return [t["id"] for t in pay_response.data["tickets"]]

    def test_canceling_a_seat_ticket_clears_its_own_seat_fk(
        self, api_client, customer, seat_map_event
    ):
        from apps.ticketing.models import Ticket

        ticket_ids = self._buy_seats(api_client, customer, seat_map_event, ["A1"])
        api_client.post(f"/api/tickets/{ticket_ids[0]}/cancel")

        ticket = Ticket.objects.get(pk=ticket_ids[0])
        assert ticket.status == Ticket.Status.CANCELED
        assert ticket.seat_id is None

    def test_reselling_a_canceled_seat_does_not_crash_payment(
        self, api_client, customer, customer2, seat_map_event
    ):
        """The exact repro: buy several seats, cancel all of them, then buy
        the same seats again as a different customer — must succeed cleanly,
        not raise IntegrityError on the second bulk_create."""
        labels = ["A1", "A2", "A3"]
        ticket_ids = self._buy_seats(api_client, customer, seat_map_event, labels)

        for ticket_id in ticket_ids:
            cancel_response = api_client.post(f"/api/tickets/{ticket_id}/cancel")
            assert cancel_response.status_code == 200, cancel_response.data

        api_client.force_authenticate(user=customer2)
        seat_ids = self._seat_ids(seat_map_event, labels)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]
        pay_response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        assert pay_response.status_code == 200, pay_response.data
        assert pay_response.data["payment_status"] == "approved"
        assert len(pay_response.data["tickets"]) == 3

    def test_canceling_an_event_with_seat_tickets_clears_their_seat_fks(
        self, api_client, organizer, customer, seat_map_event
    ):
        from apps.ticketing.models import Ticket

        ticket_ids = self._buy_seats(api_client, customer, seat_map_event, ["B1", "B2"])

        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{seat_map_event.id}", {"status": "canceled"}, format="json"
        )
        assert response.status_code == 200

        for ticket_id in ticket_ids:
            ticket = Ticket.objects.get(pk=ticket_id)
            assert ticket.status == Ticket.Status.CANCELED
            assert ticket.seat_id is None

        # And those seats must be re-sellable on a fresh (republished) event —
        # not a supported org flow via the API today, so we just assert the
        # data is clean: no lingering FK to collide with a future ticket.
        seat_ids = self._seat_ids(seat_map_event, ["B1", "B2"])
        from apps.ticketing.models import Seat

        for seat in Seat.objects.filter(pk__in=seat_ids):
            assert seat.reservation_id is None
            assert seat.held_until is None
