import pytest

from apps.ticketing.models import Ticket


@pytest.mark.django_db
class TestTicketTransfer:
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

    def test_owner_can_transfer_to_another_registered_customer(
        self, api_client, customer, customer2, published_event
    ):
        ticket_id = self._issue_ticket(api_client, customer, published_event)

        response = api_client.post(
            f"/api/tickets/{ticket_id}/transfer", {"email": customer2.email}, format="json"
        )

        assert response.status_code == 200, response.data
        ticket = Ticket.objects.get(pk=ticket_id)
        assert ticket.owner_id == customer2.id

    def test_ticket_disappears_from_sender_and_appears_for_recipient(
        self, api_client, customer, customer2, published_event
    ):
        ticket_id = self._issue_ticket(api_client, customer, published_event)
        api_client.post(f"/api/tickets/{ticket_id}/transfer", {"email": customer2.email}, format="json")

        api_client.force_authenticate(user=customer)
        mine = api_client.get("/api/tickets/mine").data
        assert ticket_id not in [t["id"] for t in mine["results"]]

        api_client.force_authenticate(user=customer2)
        mine = api_client.get("/api/tickets/mine").data
        assert ticket_id in [t["id"] for t in mine["results"]]

    def test_cannot_transfer_someone_elses_ticket(
        self, api_client, customer, customer2, published_event
    ):
        ticket_id = self._issue_ticket(api_client, customer, published_event)

        api_client.force_authenticate(user=customer2)
        response = api_client.post(
            f"/api/tickets/{ticket_id}/transfer", {"email": customer2.email}, format="json"
        )
        assert response.status_code == 404

    def test_cannot_transfer_to_unregistered_email(self, api_client, customer, published_event):
        ticket_id = self._issue_ticket(api_client, customer, published_event)

        response = api_client.post(
            f"/api/tickets/{ticket_id}/transfer",
            {"email": "ninguem@example.com"},
            format="json",
        )
        assert response.status_code == 400
        assert "email" in response.data

    def test_cannot_transfer_to_self(self, api_client, customer, published_event):
        ticket_id = self._issue_ticket(api_client, customer, published_event)

        response = api_client.post(
            f"/api/tickets/{ticket_id}/transfer", {"email": customer.email}, format="json"
        )
        assert response.status_code == 400
        assert "email" in response.data

    def test_cannot_transfer_a_used_ticket(
        self, api_client, customer, customer2, published_event, gate_user
    ):
        ticket_id = self._issue_ticket(api_client, customer, published_event)
        ticket = Ticket.objects.get(pk=ticket_id)

        api_client.force_authenticate(user=gate_user)
        api_client.post(
            "/api/gate/validate",
            {"code": ticket.public_code, "event_id": published_event.id},
            format="json",
        )

        api_client.force_authenticate(user=customer)
        response = api_client.post(
            f"/api/tickets/{ticket_id}/transfer", {"email": customer2.email}, format="json"
        )
        assert response.status_code == 409
