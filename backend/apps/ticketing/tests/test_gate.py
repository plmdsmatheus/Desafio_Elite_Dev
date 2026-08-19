from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events.models import Event
from apps.ticketing.models import Reservation, Ticket
from apps.ticketing.signing import sign_ticket_code


@pytest.fixture
def paid_ticket(published_event, customer):
    reservation = Reservation.objects.create(
        event=published_event, customer=customer, quantity=1,
        total_price=published_event.price, status=Reservation.Status.PAID,
    )
    return Ticket.objects.create(reservation=reservation, event=published_event, owner=customer)


@pytest.mark.django_db
class TestGateValidate:
    def test_valid_qr_marks_ticket_as_used(self, api_client, gate_user, published_event, paid_ticket):
        api_client.force_authenticate(user=gate_user)
        response = api_client.post(
            "/api/gate/validate",
            {"code": sign_ticket_code(paid_ticket.public_code), "event_id": published_event.id},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["result"] == "valido"

        paid_ticket.refresh_from_db()
        assert paid_ticket.status == Ticket.Status.USED
        assert paid_ticket.used_at is not None

    def test_manual_public_code_entry_also_works(self, api_client, gate_user, published_event, paid_ticket):
        api_client.force_authenticate(user=gate_user)
        response = api_client.post(
            "/api/gate/validate",
            {"code": paid_ticket.public_code, "event_id": published_event.id},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["result"] == "valido"

    def test_already_used_ticket_returns_ja_utilizado(self, api_client, gate_user, published_event, paid_ticket):
        paid_ticket.status = Ticket.Status.USED
        paid_ticket.used_at = timezone.now()
        paid_ticket.save()

        api_client.force_authenticate(user=gate_user)
        response = api_client.post(
            "/api/gate/validate",
            {"code": paid_ticket.public_code, "event_id": published_event.id},
            format="json",
        )
        assert response.data["result"] == "ja_utilizado"

    def test_ticket_from_another_event_returns_evento_errado(
        self, api_client, gate_user, organizer, paid_ticket
    ):
        other_event = Event.objects.create(
            organizer=organizer, title="Outro evento", category=Event.Category.MOVIE,
            venue_name="Cine Y", city="RJ", date_time=timezone.now(), capacity=10,
            price=Decimal("20"), status=Event.Status.PUBLISHED,
        )

        api_client.force_authenticate(user=gate_user)
        response = api_client.post(
            "/api/gate/validate",
            {"code": paid_ticket.public_code, "event_id": other_event.id},
            format="json",
        )
        assert response.data["result"] == "evento_errado"

    def test_unknown_code_returns_invalido(self, api_client, gate_user, published_event):
        api_client.force_authenticate(user=gate_user)
        response = api_client.post(
            "/api/gate/validate",
            {"code": "CODIGOFAKE", "event_id": published_event.id},
            format="json",
        )
        assert response.data["result"] == "invalido"

    def test_tampered_qr_signature_returns_invalido(self, api_client, gate_user, published_event, paid_ticket):
        tampered = sign_ticket_code(paid_ticket.public_code) + "tampered"
        api_client.force_authenticate(user=gate_user)
        response = api_client.post(
            "/api/gate/validate", {"code": tampered, "event_id": published_event.id}, format="json"
        )
        assert response.data["result"] == "invalido"

    def test_qr_signed_for_a_different_ticket_is_rejected(
        self, api_client, gate_user, published_event, paid_ticket
    ):
        """Valid signature, but for a code that never existed as this specific
        ticket — a good signature alone must not be enough to accept it."""
        forged_but_signed = sign_ticket_code("CODIGO_QUE_NAO_EXISTE")
        api_client.force_authenticate(user=gate_user)
        response = api_client.post(
            "/api/gate/validate",
            {"code": forged_but_signed, "event_id": published_event.id},
            format="json",
        )
        assert response.data["result"] == "invalido"

    def test_customer_cannot_validate_tickets(self, api_client, customer, published_event, paid_ticket):
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/gate/validate",
            {"code": paid_ticket.public_code, "event_id": published_event.id},
            format="json",
        )
        assert response.status_code == 403
