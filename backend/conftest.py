from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.events.models import Event


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organizer(db):
    return User.objects.create_user(email="organizer@test.com", password="x", role=User.Role.ORGANIZER)


@pytest.fixture
def other_organizer(db):
    return User.objects.create_user(email="other-organizer@test.com", password="x", role=User.Role.ORGANIZER)


@pytest.fixture
def customer(db):
    return User.objects.create_user(email="customer@test.com", password="x", role=User.Role.CUSTOMER)


@pytest.fixture
def customer2(db):
    return User.objects.create_user(email="customer2@test.com", password="x", role=User.Role.CUSTOMER)


@pytest.fixture
def gate_user(db):
    return User.objects.create_user(email="gate@test.com", password="x", role=User.Role.GATE)


@pytest.fixture
def published_event(organizer):
    return Event.objects.create(
        organizer=organizer,
        title="Show de Teste",
        category=Event.Category.SHOW,
        venue_name="Arena Teste",
        city="São Paulo",
        date_time=timezone.now() + timedelta(days=30),
        capacity=10,
        price=Decimal("100.00"),
        status=Event.Status.PUBLISHED,
    )


@pytest.fixture
def seat_map_event(organizer):
    from apps.ticketing.seating import generate_seats_for_event

    event = Event.objects.create(
        organizer=organizer,
        title="Sessão com Assentos Marcados",
        category=Event.Category.MOVIE,
        venue_name="Cinema Teste",
        city="São Paulo",
        date_time=timezone.now() + timedelta(days=30),
        capacity=12,
        price=Decimal("50.00"),
        status=Event.Status.PUBLISHED,
        has_seat_map=True,
    )
    generate_seats_for_event(event, seats_per_row=4)
    return event
