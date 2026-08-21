import pytest

from apps.events.models import Event
from apps.ticketing.models import Reservation, Seat, Ticket


@pytest.mark.django_db
class TestSeatMapEndpoint:
    def test_returns_every_seat_unpaginated(self, api_client, customer, seat_map_event):
        """capacity=12 > the global PAGE_SIZE=6 — the seat map must never be
        paginated, or a customer would only see the first page of seats."""
        api_client.force_authenticate(user=customer)
        response = api_client.get(f"/api/events/{seat_map_event.id}/seats")

        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) == 12
        assert all(seat["status"] == "available" for seat in response.data)

    def test_seat_labels_follow_row_and_number(self, api_client, customer, seat_map_event):
        api_client.force_authenticate(user=customer)
        response = api_client.get(f"/api/events/{seat_map_event.id}/seats")
        labels = sorted(seat["label"] for seat in response.data)
        assert labels[0] == "A1"
        assert "A4" in labels
        assert "B1" in labels  # seats_per_row=4 fixture -> row B starts at seat 5


@pytest.mark.django_db
class TestSeatReservation:
    def _seat_ids(self, event, labels):
        seats = {s.label: s.id for s in Seat.objects.filter(event=event)}
        return [seats[label] for label in labels]

    def test_reserving_seats_holds_them_as_mine_for_requester(
        self, api_client, customer, customer2, seat_map_event
    ):
        seat_ids = self._seat_ids(seat_map_event, ["A1", "A2"])
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations",
            {"event": seat_map_event.id, "seat_ids": seat_ids},
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["quantity"] == 2
        assert sorted(response.data["seats"]) == ["A1", "A2"]

        # From the requester's own perspective, held seats read as "mine"...
        seat_map = api_client.get(f"/api/events/{seat_map_event.id}/seats").data
        mine = {s["label"]: s["status"] for s in seat_map if s["label"] in ("A1", "A2")}
        assert mine == {"A1": "mine", "A2": "mine"}

        # ...but as merely "held" (not selectable) to anyone else.
        api_client.force_authenticate(user=customer2)
        seat_map = api_client.get(f"/api/events/{seat_map_event.id}/seats").data
        held = {s["label"]: s["status"] for s in seat_map if s["label"] in ("A1", "A2")}
        assert held == {"A1": "held", "A2": "held"}

    def test_cannot_reserve_a_seat_already_held_by_someone_else(
        self, api_client, customer, customer2, seat_map_event
    ):
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )

        api_client.force_authenticate(user=customer2)
        response = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )
        assert response.status_code == 409
        assert "A1" in response.data["detail"]

    def test_seat_ids_required_for_seat_map_events(self, api_client, customer, seat_map_event):
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "quantity": 2}, format="json"
        )
        assert response.status_code == 400
        assert "seat_ids" in response.data

    def test_duplicate_seat_ids_rejected(self, api_client, customer, seat_map_event):
        seat_id = self._seat_ids(seat_map_event, ["A1"])[0]
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations",
            {"event": seat_map_event.id, "seat_ids": [seat_id, seat_id]},
            format="json",
        )
        assert response.status_code == 400
        assert "seat_ids" in response.data

    def test_paying_a_seat_reservation_creates_tickets_linked_to_seats(
        self, api_client, customer, seat_map_event
    ):
        seat_ids = self._seat_ids(seat_map_event, ["A1", "A2"])
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]

        response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        assert response.status_code == 200
        seat_labels = sorted(t["seat_label"] for t in response.data["tickets"])
        assert seat_labels == ["A1", "A2"]

        seat_map = api_client.get(f"/api/events/{seat_map_event.id}/seats").data
        sold = {s["label"]: s["status"] for s in seat_map if s["label"] in ("A1", "A2")}
        assert sold == {"A1": "sold", "A2": "sold"}

    def test_declined_payment_releases_the_seat_immediately(
        self, api_client, customer, customer2, seat_map_event
    ):
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]

        pay_response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111110000"},
            format="json",
        )
        assert pay_response.data["payment_status"] == "declined"

        api_client.force_authenticate(user=customer2)
        seat_map = api_client.get(f"/api/events/{seat_map_event.id}/seats").data
        a1 = next(s for s in seat_map if s["label"] == "A1")
        assert a1["status"] == "available"

        # And customer2 can immediately grab it — no need to wait out the hold.
        response = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )
        assert response.status_code == 201

    def test_canceling_a_seat_ticket_frees_the_seat(self, api_client, customer, seat_map_event):
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]
        pay_response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        ticket_id = pay_response.data["tickets"][0]["id"]

        api_client.post(f"/api/tickets/{ticket_id}/cancel")

        seat_map = api_client.get(f"/api/events/{seat_map_event.id}/seats").data
        a1 = next(s for s in seat_map if s["label"] == "A1")
        assert a1["status"] == "available"

        event = Event.objects.get(pk=seat_map_event.id)
        assert event.tickets_available == event.capacity

    def test_expired_hold_can_be_taken_by_someone_else(
        self, api_client, customer, customer2, seat_map_event
    ):
        from datetime import timedelta

        from django.utils import timezone

        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )

        # Simulate the 10-minute hold having expired.
        Seat.objects.filter(id__in=seat_ids).update(held_until=timezone.now() - timedelta(minutes=1))

        api_client.force_authenticate(user=customer2)
        response = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )
        assert response.status_code == 201

    def test_abandoning_and_repicking_the_same_seat_works_for_the_original_holder(
        self, api_client, customer, seat_map_event
    ):
        """Bug report: pick a seat, back out of checkout before paying (no
        release call happens — the pending reservation is just left
        dangling), then try to pick the *same* seat again. Must succeed
        instead of reading as "taken" by the customer's own abandoned hold."""
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        first_reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]

        response = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )
        assert response.status_code == 201, response.data

        first_reservation = Reservation.objects.get(pk=first_reservation_id)
        assert first_reservation.status == Reservation.Status.CANCELED
        seat = Seat.objects.get(pk=seat_ids[0])
        assert seat.reservation_id == response.data["id"]

    def test_abandoned_hold_release_only_affects_the_same_customer(
        self, api_client, customer, customer2, seat_map_event
    ):
        """The stale-hold cleanup must be scoped to the requesting customer —
        it must never release a seat someone ELSE is legitimately holding."""
        seat_a1, seat_a2 = self._seat_ids(seat_map_event, ["A1", "A2"])

        api_client.force_authenticate(user=customer)
        api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": [seat_a1]}, format="json"
        )

        api_client.force_authenticate(user=customer2)
        other_reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": [seat_a2]}, format="json"
        ).data["id"]

        # customer picks A1 again (their own stale hold) — must not touch customer2's A2 hold.
        api_client.force_authenticate(user=customer)
        api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": [seat_a1]}, format="json"
        )

        assert Reservation.objects.get(pk=other_reservation_id).status == Reservation.Status.PENDING
        assert Seat.objects.get(pk=seat_a2).reservation_id == other_reservation_id

    def test_paying_for_a_reservation_superseded_by_a_fresh_pick_is_rejected(
        self, api_client, customer, seat_map_event
    ):
        """The abandoned reservation is explicitly canceled (not just
        expired) the moment the customer re-picks — paying for it afterwards
        must be rejected, not silently mint a ticket for a reservation that
        no longer holds any seat."""
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        first_reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]

        api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )

        response = api_client.post(
            f"/api/reservations/{first_reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        assert response.status_code == 409
        assert Ticket.objects.filter(reservation_id=first_reservation_id).count() == 0

    def test_paying_after_the_hold_expired_and_seat_was_taken_declines_cleanly(
        self, api_client, customer, customer2, seat_map_event
    ):
        """The original holder's hold expires, someone else grabs the seat and
        pays for it, and then the original holder's late payment attempt must
        be rejected rather than silently minting a seatless ticket."""
        from datetime import timedelta

        from django.utils import timezone

        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]

        Seat.objects.filter(id__in=seat_ids).update(held_until=timezone.now() - timedelta(minutes=1))

        api_client.force_authenticate(user=customer2)
        other_reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]
        api_client.post(
            f"/api/reservations/{other_reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )

        api_client.force_authenticate(user=customer)
        late_pay = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        assert late_pay.status_code == 409
        assert Reservation.objects.get(pk=reservation_id).status == Reservation.Status.DECLINED
        assert Ticket.objects.filter(reservation_id=reservation_id).count() == 0


@pytest.mark.django_db
class TestReservationRelease:
    """The scenario the user found in practice: customer 1 picks a seat and
    moves on to the payment step, then simply gives up — no new pick, no
    payment attempt, just abandons the page. Without an explicit release,
    customer 2 would be stuck waiting out the full 10-minute hold for a seat
    nobody is actually still trying to buy."""

    def _seat_ids(self, event, labels):
        seats = {s.label: s.id for s in Seat.objects.filter(event=event)}
        return [seats[label] for label in labels]

    def test_releasing_a_pending_reservation_frees_the_seat_immediately(
        self, api_client, customer, customer2, seat_map_event
    ):
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]

        response = api_client.post(f"/api/reservations/{reservation_id}/release")
        assert response.status_code == 200
        assert response.data["status"] == "canceled"

        seat = Seat.objects.get(pk=seat_ids[0])
        assert seat.reservation_id is None
        assert seat.held_until is None

        # customer2 can grab it right away — no need to wait out the hold.
        api_client.force_authenticate(user=customer2)
        response = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        )
        assert response.status_code == 201

    def test_release_is_scoped_to_the_owner(self, api_client, customer, customer2, seat_map_event):
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]

        api_client.force_authenticate(user=customer2)
        response = api_client.post(f"/api/reservations/{reservation_id}/release")
        assert response.status_code == 404

        seat = Seat.objects.get(pk=seat_ids[0])
        assert seat.reservation_id == reservation_id

    def test_releasing_an_already_paid_reservation_is_a_harmless_no_op(
        self, api_client, customer, seat_map_event
    ):
        """Fire-and-forget semantics: the frontend may call this on unmount
        even after a successful payment landed moments earlier — it must
        never un-sell an already-paid reservation."""
        seat_ids = self._seat_ids(seat_map_event, ["A1"])
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": seat_map_event.id, "seat_ids": seat_ids}, format="json"
        ).data["id"]
        api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )

        response = api_client.post(f"/api/reservations/{reservation_id}/release")
        assert response.status_code == 200
        assert response.data["status"] == "paid"

        seat = Seat.objects.get(pk=seat_ids[0])
        assert seat.reservation_id == reservation_id
        assert Ticket.objects.filter(reservation_id=reservation_id, seat_id=seat.id).exists()

    def test_releasing_a_general_admission_reservation_is_harmless(
        self, api_client, customer, published_event
    ):
        """Non-seat-map events don't hold any seats, but the endpoint should
        still work generically (just flips the reservation to canceled)."""
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 1}, format="json"
        ).data["id"]

        response = api_client.post(f"/api/reservations/{reservation_id}/release")
        assert response.status_code == 200
        assert response.data["status"] == "canceled"
