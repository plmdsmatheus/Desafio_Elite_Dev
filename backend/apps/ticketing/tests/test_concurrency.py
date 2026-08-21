"""Tests with real threads and real DB connections (transaction=True), to prove
the concurrency locks (select_for_update) hold under actual concurrency, not
just in theory. Slower than the rest of the suite, deliberately."""

import threading
from decimal import Decimal

import pytest
from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.events.models import Event
from apps.ticketing.models import Reservation, Seat, Ticket
from apps.ticketing.seating import generate_seats_for_event
from apps.ticketing.signing import sign_ticket_code


@pytest.mark.django_db(transaction=True)
class TestPaymentConcurrency:
    def test_two_simultaneous_payments_for_the_last_seat_only_one_wins(self):
        organizer = User.objects.create_user(email="org@test.com", password="x", role=User.Role.ORGANIZER)
        customer1 = User.objects.create_user(email="c1@test.com", password="x", role=User.Role.CUSTOMER)
        customer2 = User.objects.create_user(email="c2@test.com", password="x", role=User.Role.CUSTOMER)

        event = Event.objects.create(
            organizer=organizer, title="Última Vaga", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=1,
            price=Decimal("50"), status=Event.Status.PUBLISHED,
        )

        r1 = Reservation.objects.create(
            event=event, customer=customer1, quantity=1, total_price=Decimal("50"),
        )
        r2 = Reservation.objects.create(
            event=event, customer=customer2, quantity=1, total_price=Decimal("50"),
        )

        client1, client2 = APIClient(), APIClient()
        client1.force_authenticate(user=customer1)
        client2.force_authenticate(user=customer2)

        results = {}

        def pay(client, reservation_id, key):
            try:
                results[key] = client.post(
                    f"/api/reservations/{reservation_id}/pay",
                    {"card_number": "4111111111111111"},
                    format="json",
                )
            finally:
                # Each thread opens its own DB connection; without this it's left
                # dangling and pytest-django can't tear down the test database.
                connections.close_all()

        t1 = threading.Thread(target=pay, args=(client1, r1.id, "c1"))
        t2 = threading.Thread(target=pay, args=(client2, r2.id, "c2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        statuses = {k: r.data["reservation"]["status"] for k, r in results.items()}
        assert sorted(statuses.values()) == ["declined", "paid"]
        assert Ticket.objects.filter(event=event).count() == 1
        assert Reservation.objects.filter(event=event, status=Reservation.Status.PAID).count() == 1

    def test_two_simultaneous_pay_requests_for_the_same_reservation_only_one_succeeds(self):
        """Double click / network retry on the same payment — must not create 2
        Payments for 1 Reservation (unique constraint) or blow up with a 500."""
        organizer = User.objects.create_user(email="org4@test.com", password="x", role=User.Role.ORGANIZER)
        customer = User.objects.create_user(email="c4@test.com", password="x", role=User.Role.CUSTOMER)

        event = Event.objects.create(
            organizer=organizer, title="Pagamento Duplo", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=5,
            price=Decimal("50"), status=Event.Status.PUBLISHED,
        )
        reservation = Reservation.objects.create(
            event=event, customer=customer, quantity=1, total_price=Decimal("50"),
        )

        results = {}

        def pay(key):
            try:
                client = APIClient()
                client.force_authenticate(user=customer)
                results[key] = client.post(
                    f"/api/reservations/{reservation.id}/pay",
                    {"card_number": "4111111111111111"},
                    format="json",
                )
            finally:
                connections.close_all()

        t1 = threading.Thread(target=pay, args=("a",))
        t2 = threading.Thread(target=pay, args=("b",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        status_codes = sorted(r.status_code for r in results.values())
        assert status_codes == [200, 409], status_codes
        assert Reservation.objects.filter(id=reservation.id, status=Reservation.Status.PAID).count() == 1
        assert Ticket.objects.filter(reservation=reservation).count() == 1

    def test_ten_simultaneous_payments_for_three_seats_exactly_three_win(self):
        """Same guarantee, with more concurrency (10 threads competing for 3 seats)."""
        organizer = User.objects.create_user(email="org2@test.com", password="x", role=User.Role.ORGANIZER)
        event = Event.objects.create(
            organizer=organizer, title="Poucas Vagas", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=3,
            price=Decimal("50"), status=Event.Status.PUBLISHED,
        )

        customers = [
            User.objects.create_user(email=f"bulk{i}@test.com", password="x", role=User.Role.CUSTOMER)
            for i in range(10)
        ]
        reservations = [
            Reservation.objects.create(event=event, customer=c, quantity=1, total_price=Decimal("50"))
            for c in customers
        ]

        results = {}

        def pay(customer, reservation_id, key):
            try:
                client = APIClient()
                client.force_authenticate(user=customer)
                results[key] = client.post(
                    f"/api/reservations/{reservation_id}/pay",
                    {"card_number": "4111111111111111"},
                    format="json",
                )
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=pay, args=(customers[i], reservations[i].id, i)) for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        approved = [k for k, r in results.items() if r.data["reservation"]["status"] == "paid"]
        assert len(approved) == 3
        assert Ticket.objects.filter(event=event).count() == 3


@pytest.mark.django_db(transaction=True)
class TestGateValidationConcurrency:
    def test_two_simultaneous_validations_of_the_same_ticket_only_one_succeeds(self):
        organizer = User.objects.create_user(email="org3@test.com", password="x", role=User.Role.ORGANIZER)
        customer = User.objects.create_user(email="c3@test.com", password="x", role=User.Role.CUSTOMER)
        gate1 = User.objects.create_user(email="g1@test.com", password="x", role=User.Role.GATE)
        gate2 = User.objects.create_user(email="g2@test.com", password="x", role=User.Role.GATE)

        event = Event.objects.create(
            organizer=organizer, title="Show Concorrido", category=Event.Category.SHOW,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=10,
            price=Decimal("50"), status=Event.Status.PUBLISHED,
        )
        reservation = Reservation.objects.create(
            event=event, customer=customer, quantity=1, total_price=Decimal("50"),
            status=Reservation.Status.PAID,
        )
        ticket = Ticket.objects.create(reservation=reservation, event=event, owner=customer)
        signed_code = sign_ticket_code(ticket.public_code)

        client1, client2 = APIClient(), APIClient()
        client1.force_authenticate(user=gate1)
        client2.force_authenticate(user=gate2)

        results = {}

        def validate(client, key):
            try:
                results[key] = client.post(
                    "/api/gate/validate", {"code": signed_code, "event_id": event.id}, format="json"
                )
            finally:
                connections.close_all()

        t1 = threading.Thread(target=validate, args=(client1, "g1"))
        t2 = threading.Thread(target=validate, args=(client2, "g2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        outcomes = sorted(r.data["result"] for r in results.values())
        assert outcomes == ["ja_utilizado", "valido"]

        ticket.refresh_from_db()
        assert ticket.status == Ticket.Status.USED


@pytest.mark.django_db(transaction=True)
class TestSeatHoldConcurrency:
    def test_two_customers_racing_for_the_same_seat_only_one_wins(self):
        """The scenario the user explicitly asked to be safe against: two
        people picking the same seat at (as close to) the same instant. The
        select_for_update in hold_seats must let exactly one of them claim
        it — never both, never neither."""
        organizer = User.objects.create_user(email="seat-org@test.com", password="x", role=User.Role.ORGANIZER)
        customer1 = User.objects.create_user(email="seat-c1@test.com", password="x", role=User.Role.CUSTOMER)
        customer2 = User.objects.create_user(email="seat-c2@test.com", password="x", role=User.Role.CUSTOMER)

        event = Event.objects.create(
            organizer=organizer, title="Cinema Concorrido", category=Event.Category.MOVIE,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=4,
            price=Decimal("40"), status=Event.Status.PUBLISHED, has_seat_map=True,
        )
        generate_seats_for_event(event, seats_per_row=4)
        seat_id = Seat.objects.get(event=event, row_label="A", number=1).id

        client1, client2 = APIClient(), APIClient()
        client1.force_authenticate(user=customer1)
        client2.force_authenticate(user=customer2)

        results = {}

        def reserve(client, key):
            try:
                results[key] = client.post(
                    "/api/reservations",
                    {"event": event.id, "seat_ids": [seat_id]},
                    format="json",
                )
            finally:
                connections.close_all()

        t1 = threading.Thread(target=reserve, args=(client1, "c1"))
        t2 = threading.Thread(target=reserve, args=(client2, "c2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        status_codes = sorted(r.status_code for r in results.values())
        assert status_codes == [201, 409], status_codes

        seat = Seat.objects.get(pk=seat_id)
        winner_key = next(k for k, r in results.items() if r.status_code == 201)
        winner = {"c1": customer1, "c2": customer2}[winner_key]
        assert seat.reservation.customer_id == winner.id
        assert Reservation.objects.filter(event=event, customer=winner).count() == 1

    def test_ten_customers_racing_for_the_same_seat_bundle_only_one_wins(self):
        """More contention (10 threads), and over a multi-seat bundle instead
        of a single seat: everyone requests the identical 3 seats at once, so
        hold_seats' all-or-nothing locking must let exactly one requester
        claim the whole bundle — never a partial split between two winners."""
        organizer = User.objects.create_user(email="seat-org2@test.com", password="x", role=User.Role.ORGANIZER)
        event = Event.objects.create(
            organizer=organizer, title="Estreia Concorrida", category=Event.Category.MOVIE,
            venue_name="V", city="SP", date_time=timezone.now(), capacity=3,
            price=Decimal("40"), status=Event.Status.PUBLISHED, has_seat_map=True,
        )
        generate_seats_for_event(event, seats_per_row=3)
        seat_ids = list(Seat.objects.filter(event=event).values_list("id", flat=True))
        assert len(seat_ids) == 3

        customers = [
            User.objects.create_user(email=f"seat-bulk{i}@test.com", password="x", role=User.Role.CUSTOMER)
            for i in range(10)
        ]

        results = {}

        def reserve(client, key):
            try:
                results[key] = client.post(
                    "/api/reservations",
                    {"event": event.id, "seat_ids": seat_ids},
                    format="json",
                )
            finally:
                connections.close_all()

        clients = []
        for customer in customers:
            client = APIClient()
            client.force_authenticate(user=customer)
            clients.append(client)

        threads = [threading.Thread(target=reserve, args=(clients[i], i)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        won = [k for k, r in results.items() if r.status_code == 201]
        lost = [r.status_code for r in results.values() if r.status_code != 201]
        assert len(won) == 1
        assert lost == [409] * 9
        assert Reservation.objects.filter(event=event).count() == 1
        assert Seat.objects.filter(event=event, reservation__isnull=False).count() == 3
