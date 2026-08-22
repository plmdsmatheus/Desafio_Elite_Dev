import json

import pytest

from apps.ticketing.models import Seat


def _first_payload(response):
    """Reads only the first `data:` event off a StreamingHttpResponse. The
    generator yields before its first `time.sleep()` (see
    apps.ticketing.sse.stream_while_changed), so this runs instantly —
    no real time passes."""
    chunk = next(iter(response.streaming_content))
    text = chunk.decode().removeprefix("data:").strip()
    return json.loads(text)


@pytest.mark.django_db
class TestAvailabilityStream:
    def test_first_event_matches_current_state(self, api_client, customer, published_event):
        api_client.force_authenticate(user=customer)
        response = api_client.get(f"/api/events/{published_event.id}/availability/stream")

        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"
        payload = _first_payload(response)
        assert payload == {
            "tickets_available": published_event.capacity,
            "tickets_sold": 0,
            "capacity": published_event.capacity,
        }

    def test_reflects_tickets_already_sold(self, api_client, customer, published_event):
        api_client.force_authenticate(user=customer)
        reservation_id = api_client.post(
            "/api/reservations", {"event": published_event.id, "quantity": 2}, format="json"
        ).data["id"]
        api_client.post(
            f"/api/reservations/{reservation_id}/pay",
            {"card_number": "4111111111111111"},
            format="json",
        )

        response = api_client.get(f"/api/events/{published_event.id}/availability/stream")
        payload = _first_payload(response)
        assert payload["tickets_sold"] == 2
        assert payload["tickets_available"] == published_event.capacity - 2

    def test_requires_customer_role(self, api_client, organizer, published_event):
        api_client.force_authenticate(user=organizer)
        response = api_client.get(f"/api/events/{published_event.id}/availability/stream")
        assert response.status_code == 403

    def test_404s_for_missing_event(self, api_client, customer):
        api_client.force_authenticate(user=customer)
        response = api_client.get("/api/events/999999/availability/stream")
        assert response.status_code == 404


@pytest.mark.django_db
class TestSeatMapStream:
    def test_first_event_matches_current_state(self, api_client, customer, seat_map_event):
        api_client.force_authenticate(user=customer)
        response = api_client.get(f"/api/events/{seat_map_event.id}/seats/stream")

        assert response.status_code == 200
        assert response["Content-Type"] == "text/event-stream"
        payload = _first_payload(response)
        assert len(payload) == 12
        assert all(seat["status"] == "available" for seat in payload)

    def test_reflects_a_held_seat(self, api_client, customer, seat_map_event):
        seat_id = Seat.objects.filter(event=seat_map_event, row_label="A", number=1).get().id
        api_client.force_authenticate(user=customer)
        api_client.post(
            "/api/reservations",
            {"event": seat_map_event.id, "seat_ids": [seat_id]},
            format="json",
        )

        response = api_client.get(f"/api/events/{seat_map_event.id}/seats/stream")
        payload = _first_payload(response)
        held = next(s for s in payload if s["id"] == seat_id)
        assert held["status"] == "mine"

    def test_requires_customer_role(self, api_client, organizer, seat_map_event):
        api_client.force_authenticate(user=organizer)
        response = api_client.get(f"/api/events/{seat_map_event.id}/seats/stream")
        assert response.status_code == 403

    def test_404s_for_missing_event(self, api_client, customer):
        api_client.force_authenticate(user=customer)
        response = api_client.get("/api/events/999999/seats/stream")
        assert response.status_code == 404
