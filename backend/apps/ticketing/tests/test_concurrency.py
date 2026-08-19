"""Testes com threads reais + conexões de DB reais (transaction=True), pra provar que
as travas de concorrência (select_for_update) seguram sob concorrência de verdade —
não só "no papel". Mais lentos que o resto da suíte, de propósito."""

import threading
from decimal import Decimal

import pytest
from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.events.models import Event
from apps.ticketing.models import Reservation, Ticket
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
                # cada thread abre sua própria conexão de DB; sem isso ela fica
                # pendurada e o pytest-django não consegue derrubar o banco de teste.
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

    def test_ten_simultaneous_payments_for_three_seats_exactly_three_win(self):
        """Mesma garantia, com mais concorrência (10 threads disputando 3 vagas)."""
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
