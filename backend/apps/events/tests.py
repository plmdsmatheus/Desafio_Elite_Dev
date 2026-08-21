from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events.models import Event


@pytest.mark.django_db
class TestPublicListing:
    def test_only_published_events_are_public(self, api_client, organizer):
        Event.objects.create(
            organizer=organizer, title="Publicado", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=10,
            price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        Event.objects.create(
            organizer=organizer, title="Rascunho", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=10,
            price=Decimal("10"), status=Event.Status.DRAFT,
        )

        response = api_client.get("/api/events/")

        assert response.status_code == 200
        titles = [e["title"] for e in response.data["results"]]
        assert "Publicado" in titles
        assert "Rascunho" not in titles

    def test_search_filters_by_title(self, api_client, published_event):
        response = api_client.get("/api/events/", {"q": "Show de"})
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

        response = api_client.get("/api/events/", {"q": "não existe"})
        assert response.data["results"] == []


@pytest.mark.django_db
class TestOrganizerCreatesEvents:
    def test_organizer_can_create_event(self, api_client, organizer):
        api_client.force_authenticate(user=organizer)
        response = api_client.post(
            "/api/events/",
            {
                "title": "Novo Evento",
                "category": "show",
                "venue_name": "Arena",
                "city": "SP",
                "date_time": (timezone.now() + timedelta(days=10)).isoformat(),
                "capacity": 50,
                "price": "99.90",
                "status": "published",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["id"] is not None
        assert response.data["tickets_available"] == 50

    def test_customer_cannot_create_event(self, api_client, customer):
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/events/",
            {
                "title": "Não deveria criar", "category": "show", "venue_name": "Arena",
                "city": "SP", "date_time": timezone.now().isoformat(), "capacity": 10,
                "price": "10.00", "status": "published",
            },
            format="json",
        )
        assert response.status_code == 403

    def test_capacity_must_be_at_least_one(self, api_client, organizer):
        api_client.force_authenticate(user=organizer)
        response = api_client.post(
            "/api/events/",
            {
                "title": "Capacidade inválida", "category": "show", "venue_name": "Arena",
                "city": "SP", "date_time": timezone.now().isoformat(), "capacity": 0,
                "price": "10.00", "status": "published",
            },
            format="json",
        )
        assert response.status_code == 400
        assert "capacity" in response.data


@pytest.mark.django_db
class TestEventOwnership:
    def test_owner_can_edit_own_event(self, api_client, organizer, published_event):
        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"price": "150.00"}, format="json"
        )
        assert response.status_code == 200
        assert response.data["price"] == "150.00"

    def test_other_organizer_cannot_edit_gets_404(self, api_client, other_organizer, published_event):
        api_client.force_authenticate(user=other_organizer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"price": "1.00"}, format="json"
        )
        assert response.status_code == 404

    def test_customer_cannot_edit_gets_403(self, api_client, customer, published_event):
        api_client.force_authenticate(user=customer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"price": "1.00"}, format="json"
        )
        assert response.status_code == 403

    def test_cannot_reduce_capacity_below_sold(self, api_client, organizer, published_event, customer):
        from apps.ticketing.models import Reservation, Ticket

        reservation = Reservation.objects.create(
            event=published_event, customer=customer, quantity=3,
            total_price=Decimal("300"), status=Reservation.Status.PAID,
        )
        Ticket.objects.bulk_create(
            [Ticket(reservation=reservation, event=published_event, owner=customer) for _ in range(3)]
        )

        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"capacity": 2}, format="json"
        )
        assert response.status_code == 400
        assert "capacity" in response.data

    def test_organizer_events_list_only_shows_own(self, api_client, organizer, other_organizer, published_event):
        api_client.force_authenticate(user=other_organizer)
        response = api_client.get("/api/organizer/events")
        assert response.status_code == 200
        ids = [e["id"] for e in response.data["results"]]
        assert published_event.id not in ids

    def test_canceling_an_event_invalidates_its_valid_tickets(
        self, api_client, organizer, published_event, customer
    ):
        from apps.ticketing.models import Reservation, Ticket

        reservation = Reservation.objects.create(
            event=published_event, customer=customer, quantity=2,
            total_price=Decimal("200"), status=Reservation.Status.PAID,
        )
        tickets = Ticket.objects.bulk_create(
            [Ticket(reservation=reservation, event=published_event, owner=customer) for _ in range(2)]
        )
        used_ticket = tickets[0]
        used_ticket.status = Ticket.Status.USED
        used_ticket.used_at = timezone.now()
        used_ticket.save(update_fields=["status", "used_at"])

        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"status": "canceled"}, format="json"
        )
        assert response.status_code == 200

        tickets[1].refresh_from_db()
        assert tickets[1].status == Ticket.Status.CANCELED
        # Already-used tickets aren't retroactively changed — they already happened.
        used_ticket.refresh_from_db()
        assert used_ticket.status == Ticket.Status.USED

    def test_canceling_an_already_canceled_event_is_a_harmless_no_op(
        self, api_client, organizer, published_event, customer
    ):
        from apps.ticketing.models import Reservation, Ticket

        reservation = Reservation.objects.create(
            event=published_event, customer=customer, quantity=1,
            total_price=Decimal("100"), status=Reservation.Status.PAID,
        )
        ticket = Ticket.objects.create(reservation=reservation, event=published_event, owner=customer)

        api_client.force_authenticate(user=organizer)
        api_client.patch(f"/api/events/{published_event.id}", {"status": "canceled"}, format="json")
        # Customer transfers is blocked on a canceled ticket — simulate someone
        # else's ticket staying VALID some other way isn't possible here, so
        # just confirm a second cancel-save doesn't error and stays canceled.
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"price": "1.00"}, format="json"
        )
        assert response.status_code == 200
        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.CANCELED


@pytest.mark.django_db
class TestEffectiveStatus:
    def test_published_future_event_reads_as_published(self, api_client, published_event):
        response = api_client.get(f"/api/events/{published_event.id}")
        assert response.data["status"] == "published"
        assert response.data["effective_status"] == "published"

    def test_published_past_event_reads_as_completed(self, api_client, organizer):
        event = Event.objects.create(
            organizer=organizer, title="Já Rolou", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() - timedelta(days=1),
            capacity=10, price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        response = api_client.get(f"/api/events/{event.id}")
        assert response.data["status"] == "published"
        assert response.data["effective_status"] == "completed"

    def test_canceled_past_event_stays_canceled_not_completed(self, api_client, organizer):
        event = Event.objects.create(
            organizer=organizer, title="Cancelado no Passado", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() - timedelta(days=1),
            capacity=10, price=Decimal("10"), status=Event.Status.CANCELED,
        )
        api_client.force_authenticate(user=organizer)
        response = api_client.get(f"/api/events/{event.id}")
        assert response.data["effective_status"] == "canceled"

    def test_draft_past_event_stays_draft_not_completed(self, api_client, organizer):
        event = Event.objects.create(
            organizer=organizer, title="Rascunho Antigo", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() - timedelta(days=1),
            capacity=10, price=Decimal("10"), status=Event.Status.DRAFT,
        )
        api_client.force_authenticate(user=organizer)
        response = api_client.get(f"/api/events/{event.id}")
        assert response.data["effective_status"] == "draft"
