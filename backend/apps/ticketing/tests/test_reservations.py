import pytest

from apps.ticketing.models import Reservation


@pytest.mark.django_db
class TestReservationCreate:
    def test_customer_can_reserve(self, api_client, customer, published_event):
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 2}, format="json"
        )
        assert response.status_code == 201, response.data
        assert response.data["status"] == "pending"
        assert response.data["quantity"] == 2
        assert response.data["total_price"] == "200.00"

    def test_organizer_cannot_reserve(self, api_client, organizer, published_event):
        api_client.force_authenticate(user=organizer)
        response = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 1}, format="json"
        )
        assert response.status_code == 403

    def test_cannot_reserve_more_than_available_soft_check(self, api_client, customer, published_event):
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations",
            {"event": published_event.id, "quantity": published_event.capacity + 1},
            format="json",
        )
        assert response.status_code == 400
        assert "quantity" in response.data

    def test_cannot_reserve_unpublished_event(self, api_client, customer, published_event):
        published_event.status = published_event.Status.DRAFT
        published_event.save()

        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 1}, format="json"
        )
        assert response.status_code == 400
        assert "event" in response.data

    def test_cannot_reserve_an_event_that_already_happened(self, api_client, customer, published_event):
        from datetime import timedelta

        from django.utils import timezone

        published_event.date_time = timezone.now() - timedelta(hours=1)
        published_event.save()

        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 1}, format="json"
        )
        assert response.status_code == 400
        assert "event" in response.data


@pytest.mark.django_db
class TestReservationPayBlocksCanceledEvent:
    def test_paying_for_an_event_canceled_after_reservation_is_declined(
        self, api_client, customer, published_event
    ):
        """The event can be canceled by the organizer between reservation
        creation and payment — the payment must not silently mint a ticket
        for an event that's no longer happening."""
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 1}, format="json"
        ).data["id"]

        published_event.status = published_event.Status.CANCELED
        published_event.save()

        response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["payment_status"] == "declined"
        assert response.data["tickets"] == []

    def test_quantity_must_be_at_least_one(self, api_client, customer, published_event):
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 0}, format="json"
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestReservationPay:
    def _reserve(self, api_client, customer, event, quantity=1):
        api_client.force_authenticate(user=customer)
        response = api_client.post(
            "/api/reservations", {"event": event.id, "quantity": quantity}, format="json"
        )
        return response.data["id"]

    def test_normal_card_approves_and_issues_tickets(self, api_client, customer, published_event):
        reservation_id = self._reserve(api_client, customer, published_event, quantity=2)

        response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["payment_status"] == "approved"
        assert response.data["reservation"]["status"] == "paid"
        assert len(response.data["tickets"]) == 2

    def test_card_ending_in_0000_is_declined_and_issues_no_tickets(
        self, api_client, customer, published_event
    ):
        from apps.ticketing.models import Ticket

        reservation_id = self._reserve(api_client, customer, published_event, quantity=1)

        response = api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "5555555555550000"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["payment_status"] == "declined"
        assert response.data["reservation"]["status"] == "declined"
        assert response.data["tickets"] == []
        assert Ticket.objects.filter(reservation_id=reservation_id).count() == 0

    def test_cannot_pay_someone_elses_reservation(
        self, api_client, customer, customer2, published_event
    ):
        reservation_id = self._reserve(api_client, customer, published_event)

        api_client.force_authenticate(user=customer2)
        response = api_client.post(
            f"/api/reservations/{reservation_id}/pay", {"card_number": "4111111111111111"}, format="json"
        )
        assert response.status_code == 404

    def test_cannot_pay_an_already_paid_reservation_again(self, api_client, customer, published_event):
        reservation_id = self._reserve(api_client, customer, published_event)
        api_client.force_authenticate(user=customer)
        api_client.post(
            f"/api/reservations/{reservation_id}/pay", {"card_number": "4111111111111111"}, format="json"
        )

        response = api_client.post(
            f"/api/reservations/{reservation_id}/pay", {"card_number": "4111111111111111"}, format="json"
        )
        assert response.status_code == 409  # no longer "pending"

    def test_capacity_is_rechecked_at_payment_time(self, api_client, customer, customer2, published_event):
        """The reservation itself doesn't hold stock — only an approved payment
        does. Checked here sequentially; the real concurrent version (with
        actual threads) lives in test_concurrency.py."""
        published_event.capacity = 1
        published_event.save()

        r1 = self._reserve(api_client, customer, published_event, quantity=1)
        r2 = self._reserve(api_client, customer2, published_event, quantity=1)

        api_client.force_authenticate(user=customer)
        resp1 = api_client.post(f"/api/reservations/{r1}/pay", {"card_number": "4111111111111111"}, format="json")
        assert resp1.data["payment_status"] == "approved"

        api_client.force_authenticate(user=customer2)
        resp2 = api_client.post(f"/api/reservations/{r2}/pay", {"card_number": "4111111111111111"}, format="json")
        assert resp2.data["payment_status"] == "declined"
        assert resp2.data["reservation"]["status"] == "declined"

        assert Reservation.objects.filter(event=published_event, status="paid").count() == 1
