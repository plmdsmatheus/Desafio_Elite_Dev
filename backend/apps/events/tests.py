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
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=1), capacity=10,
            price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        Event.objects.create(
            organizer=organizer, title="Rascunho", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=1), capacity=10,
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

    def test_sold_out_events_dont_bury_an_available_one_on_page_2(self, api_client, organizer, customer):
        """Reported in practice: 7 published events, 6 already sold out — with
        a fixed page size (6) and date_time as the only ordering, the one
        event still worth buying could land on page 2 depending on its date.
        Sold-out events must sort after available ones so the buyable event
        is always on page 1."""
        from apps.ticketing.models import Reservation, Ticket

        for i in range(6):
            sold_out = Event.objects.create(
                organizer=organizer, title=f"Esgotado {i}", category=Event.Category.SHOW,
                venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=i),
                capacity=1, price=Decimal("10"), status=Event.Status.PUBLISHED,
            )
            reservation = Reservation.objects.create(
                event=sold_out, customer=customer, quantity=1,
                total_price=Decimal("10"), status=Reservation.Status.PAID,
            )
            Ticket.objects.create(reservation=reservation, event=sold_out, owner=customer)

        available = Event.objects.create(
            organizer=organizer, title="Ainda Disponível", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=100),
            capacity=10, price=Decimal("10"), status=Event.Status.PUBLISHED,
        )

        response = api_client.get("/api/events/", {"show_unavailable": "true"})
        assert response.status_code == 200
        first_page_titles = [e["title"] for e in response.data["results"]]
        assert available.title in first_page_titles

    def test_completed_events_sort_after_sold_out_ones(self, api_client, organizer, customer):
        """Reported in practice: past ("realizado") events showing up mixed in
        with upcoming ones confused buyers. They must rank last — below even
        sold-out-but-still-upcoming events — regardless of date_time."""
        completed = Event.objects.create(
            organizer=organizer, title="Já Aconteceu", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() - timedelta(days=1),
            capacity=10, price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        sold_out = Event.objects.create(
            organizer=organizer, title="Esgotado Mas Futuro", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=1),
            capacity=1, price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        from apps.ticketing.models import Reservation, Ticket

        reservation = Reservation.objects.create(
            event=sold_out, customer=customer, quantity=1,
            total_price=Decimal("10"), status=Reservation.Status.PAID,
        )
        Ticket.objects.create(reservation=reservation, event=sold_out, owner=customer)

        response = api_client.get("/api/events/", {"show_unavailable": "true"})
        assert response.status_code == 200
        titles = [e["title"] for e in response.data["results"]]
        assert titles.index(sold_out.title) < titles.index(completed.title)

    def test_show_unavailable_defaults_to_excluding_sold_out_and_completed(
        self, api_client, organizer, customer
    ):
        """The other side of the two tests above: by default (no
        show_unavailable param), sold-out and completed events shouldn't
        show up in the results at all — not just sorted last."""
        from apps.ticketing.models import Reservation, Ticket

        available = Event.objects.create(
            organizer=organizer, title="Disponível", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=1),
            capacity=10, price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        sold_out = Event.objects.create(
            organizer=organizer, title="Esgotado", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=1),
            capacity=1, price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        reservation = Reservation.objects.create(
            event=sold_out, customer=customer, quantity=1,
            total_price=Decimal("10"), status=Reservation.Status.PAID,
        )
        Ticket.objects.create(reservation=reservation, event=sold_out, owner=customer)
        completed = Event.objects.create(
            organizer=organizer, title="Realizado", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() - timedelta(days=1),
            capacity=10, price=Decimal("10"), status=Event.Status.PUBLISHED,
        )

        response = api_client.get("/api/events/")
        assert response.status_code == 200
        titles = [e["title"] for e in response.data["results"]]
        assert titles == [available.title]
        assert response.data["count"] == 1

        response = api_client.get("/api/events/", {"show_unavailable": "true"})
        titles = {e["title"] for e in response.data["results"]}
        assert titles == {available.title, sold_out.title, completed.title}
        assert response.data["count"] == 3


@pytest.mark.django_db
class TestEventCities:
    def test_returns_distinct_sorted_cities_from_published_events_only(self, api_client, organizer):
        Event.objects.create(
            organizer=organizer, title="A", category=Event.Category.SHOW,
            venue_name="V", city="São Paulo", date_time=timezone.now(), capacity=10,
            price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        Event.objects.create(
            organizer=organizer, title="B", category=Event.Category.SHOW,
            venue_name="V", city="São Paulo", date_time=timezone.now(), capacity=10,
            price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        Event.objects.create(
            organizer=organizer, title="C", category=Event.Category.SHOW,
            venue_name="V", city="Belo Horizonte", date_time=timezone.now(), capacity=10,
            price=Decimal("10"), status=Event.Status.PUBLISHED,
        )
        Event.objects.create(
            organizer=organizer, title="Rascunho", category=Event.Category.SHOW,
            venue_name="V", city="Curitiba", date_time=timezone.now(), capacity=10,
            price=Decimal("10"), status=Event.Status.DRAFT,
        )

        response = api_client.get("/api/events/cities")
        assert response.status_code == 200
        assert response.data == ["Belo Horizonte", "São Paulo"]


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
        # Publishing is a deliberate, separate action — a new event always
        # starts as a draft, even if "published" was sent at creation time.
        assert response.data["status"] == "draft"

    def test_organizer_can_set_age_rating_on_creation(self, api_client, organizer):
        api_client.force_authenticate(user=organizer)
        response = api_client.post(
            "/api/events/",
            {
                "title": "Filme com classificação", "category": "movie", "venue_name": "Cine",
                "city": "SP", "date_time": (timezone.now() + timedelta(days=10)).isoformat(),
                "capacity": 50, "price": "30.00", "age_rating": "14",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["age_rating"] == "14"

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
            f"/api/events/{published_event.id}", {"venue_name": "Novo Local"}, format="json"
        )
        assert response.status_code == 200
        assert response.data["venue_name"] == "Novo Local"

    def test_other_organizer_cannot_edit_gets_404(self, api_client, other_organizer, published_event):
        api_client.force_authenticate(user=other_organizer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"venue_name": "X"}, format="json"
        )
        assert response.status_code == 404

    def test_customer_cannot_edit_gets_403(self, api_client, customer, published_event):
        api_client.force_authenticate(user=customer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"venue_name": "X"}, format="json"
        )
        assert response.status_code == 403

    def test_draft_event_accepts_edits_to_any_field(self, api_client, organizer):
        draft = Event.objects.create(
            organizer=organizer, title="Rascunho", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=10),
            capacity=10, price=Decimal("10"), status=Event.Status.DRAFT,
        )
        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{draft.id}",
            {"title": "Novo Título", "price": "55.00", "category": "movie"},
            format="json",
        )
        assert response.status_code == 200, response.data
        assert response.data["title"] == "Novo Título"
        assert response.data["price"] == "55.00"
        assert response.data["category"] == "movie"

    def test_draft_cannot_jump_straight_to_canceled(self, api_client, organizer):
        draft = Event.objects.create(
            organizer=organizer, title="Rascunho", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=10),
            capacity=10, price=Decimal("10"), status=Event.Status.DRAFT,
        )
        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{draft.id}", {"status": "canceled"}, format="json"
        )
        assert response.status_code == 400
        assert "status" in response.data

    def test_draft_can_be_published(self, api_client, organizer):
        draft = Event.objects.create(
            organizer=organizer, title="Rascunho", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now() + timedelta(days=10),
            capacity=10, price=Decimal("10"), status=Event.Status.DRAFT,
        )
        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{draft.id}", {"status": "published"}, format="json"
        )
        assert response.status_code == 200
        assert response.data["status"] == "published"

    def test_published_event_rejects_changes_outside_date_and_location(
        self, api_client, organizer, published_event, customer
    ):
        """Was previously about reducing capacity below what's sold — now
        capacity (like every other non-location field) is locked outright
        the moment an event is published, regardless of sales."""
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

    def test_published_event_rejects_age_rating_change(self, api_client, organizer, published_event):
        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"age_rating": "18"}, format="json"
        )
        assert response.status_code == 400
        assert "age_rating" in response.data

    def test_published_event_accepts_date_and_location_changes_together(
        self, api_client, organizer, published_event
    ):
        api_client.force_authenticate(user=organizer)
        new_date = (timezone.now() + timedelta(days=60)).isoformat()
        response = api_client.patch(
            f"/api/events/{published_event.id}",
            {
                "date_time": new_date,
                "venue_name": "Novo Local",
                "address": "Rua Nova, 123",
                "city": "Nova Cidade",
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        assert response.data["venue_name"] == "Novo Local"
        assert response.data["city"] == "Nova Cidade"

    def test_published_event_cannot_go_back_to_draft(self, api_client, organizer, published_event):
        api_client.force_authenticate(user=organizer)
        response = api_client.patch(
            f"/api/events/{published_event.id}", {"status": "draft"}, format="json"
        )
        assert response.status_code == 400
        assert "status" in response.data

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

    def test_canceled_event_rejects_any_further_changes(
        self, api_client, organizer, published_event, customer
    ):
        """Canceled is a terminal state — unlike the old free-form status
        field, nothing about a canceled event can be edited afterwards, not
        even canceling it again."""
        from apps.ticketing.models import Reservation, Ticket

        reservation = Reservation.objects.create(
            event=published_event, customer=customer, quantity=1,
            total_price=Decimal("100"), status=Reservation.Status.PAID,
        )
        ticket = Ticket.objects.create(reservation=reservation, event=published_event, owner=customer)

        api_client.force_authenticate(user=organizer)
        api_client.patch(f"/api/events/{published_event.id}", {"status": "canceled"}, format="json")

        response = api_client.patch(
            f"/api/events/{published_event.id}", {"venue_name": "Outro Local"}, format="json"
        )
        assert response.status_code == 400

        response = api_client.patch(
            f"/api/events/{published_event.id}", {"status": "canceled"}, format="json"
        )
        assert response.status_code == 400

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
