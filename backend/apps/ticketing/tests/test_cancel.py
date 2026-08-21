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
