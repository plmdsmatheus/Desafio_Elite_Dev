from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Reservation, Seat, Ticket

# How long a selected-but-unpaid seat stays off-limits to everyone else.
# There's no background sweep for expired holds (no Celery in this project) —
# every availability check below simply treats `held_until <= now` as free,
# so an abandoned hold self-heals the moment someone else tries to take it.
SEAT_HOLD_MINUTES = 10
DEFAULT_SEATS_PER_ROW = 10


class SeatsUnavailable(Exception):
    """One or more requested seats can't be held right now — already sold,
    already held by someone else, or don't exist for this event. This means
    the client's seat map view is stale, not that the request was malformed —
    callers map it to an HTTP 409 so the frontend knows to refetch and let
    the customer pick again."""


def _row_label(index: int) -> str:
    """0->A, 25->Z, 26->AA, 27->AB, ... spreadsheet-style, for venues with
    more than 26 rows."""
    index += 1
    label = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def generate_seats_for_event(event, seats_per_row=DEFAULT_SEATS_PER_ROW):
    """Creates the Seat grid for an event from its capacity. Idempotent — a
    no-op if seats already exist, since resizing a seat map after seats may
    already be sold isn't a supported flow (capacity itself already can't be
    lowered below tickets_sold — see EventWriteSerializer.validate)."""
    if event.seats.exists():
        return

    seats_per_row = max(min(seats_per_row, event.capacity), 1)
    seats = [
        Seat(event=event, row_label=_row_label(i // seats_per_row), number=(i % seats_per_row) + 1)
        for i in range(event.capacity)
    ]
    Seat.objects.bulk_create(seats)


def release_stale_holds_for_customer(event, customer):
    """Frees any seats the customer is still holding through an earlier
    PENDING reservation for this event, and cancels those reservations.
    Called right before every fresh seat pick so backing out of checkout
    without paying — then coming back, even for the exact same seat — just
    works, instead of the seat reading as "taken" by the customer's own
    abandoned hold (the natural 10-minute expiry would eventually clear it
    too, but there's no reason to make the customer wait for themselves)."""
    stale = Reservation.objects.filter(
        event=event, customer=customer, status=Reservation.Status.PENDING
    )
    Seat.objects.filter(reservation__in=stale).update(reservation=None, held_until=None)
    stale.update(status=Reservation.Status.CANCELED)


def release_reservation_hold(reservation):
    """Explicitly abandons a still-PENDING reservation: frees any seats it
    holds and marks it canceled. Idempotent no-op if the reservation isn't
    pending anymore (already paid/declined/canceled) — safe to call from a
    fire-and-forget "I'm leaving" signal without checking state first."""
    if reservation.status != Reservation.Status.PENDING:
        return
    Seat.objects.filter(reservation=reservation).update(reservation=None, held_until=None)
    reservation.status = Reservation.Status.CANCELED
    reservation.save(update_fields=["status", "updated_at"])


def cancel_ticket_and_release_seat(ticket):
    """Cancels a single still-valid ticket and, if it holds a seat, fully
    detaches it — clearing both the seat's own hold state AND the ticket's
    own `seat` FK. Clearing only the seat isn't enough: `Ticket.seat` is a
    one-to-one column backed by a database-level unique constraint, so a
    canceled ticket that still points at a seat permanently occupies that
    seat's one and only slot — a future ticket for the same seat would fail
    to insert with a duplicate-key error (this was a real bug: canceling a
    batch of seat tickets left every one of those seats unsellable forever).
    Caller is responsible for any surrounding transaction/locking."""
    seat_id = ticket.seat_id
    ticket.status = Ticket.Status.CANCELED
    ticket.seat = None
    ticket.save(update_fields=["status", "seat"])
    if seat_id:
        Seat.objects.filter(pk=seat_id).update(reservation=None, held_until=None)


def cancel_valid_tickets_for_event(event):
    """Bulk version of cancel_ticket_and_release_seat, for when an entire
    event gets canceled — same reasoning: a still-valid ticket's `seat` FK
    must be cleared, not just the seat's own hold state, or that seat can
    never be sold again."""
    with transaction.atomic():
        valid_tickets = Ticket.objects.filter(event=event, status=Ticket.Status.VALID)
        seat_ids = list(valid_tickets.exclude(seat_id=None).values_list("seat_id", flat=True))
        valid_tickets.update(status=Ticket.Status.CANCELED, seat=None)
        if seat_ids:
            Seat.objects.filter(pk__in=seat_ids).update(reservation=None, held_until=None)


def hold_seats(event, seat_ids, reservation):
    """Locks `seat_ids` for `reservation` (an unsaved Reservation instance)
    and saves it — all inside one transaction. Seats are select_for_update
    (ordered by id, so two requests over overlapping sets can't deadlock each
    other), then checked one by one: sold (has a non-canceled ticket), or
    held by a *still-live* pending reservation (an expired hold is free no
    matter what the stale FK says). If any seat fails that check, the whole
    transaction rolls back and SeatsUnavailable is raised — either the whole
    selection succeeds or none of it does, and nothing else can slip in
    between the check and the claim because the rows are locked throughout."""
    now = timezone.now()

    with transaction.atomic():
        # No select_related here on purpose: Postgres only re-fetches the
        # FOR-UPDATE'd table after waiting on a lock — a JOINed table in the
        # *same* statement can still reflect the pre-wait snapshot, so a seat
        # another transaction just claimed while we waited would look
        # unheld. Ticket/Reservation are re-queried fresh below, after the
        # lock is confirmed held, which always sees the committed data.
        seats = list(
            # `of=("self",)`: restrict the lock to the seat rows themselves.
            Seat.objects.select_for_update(of=("self",))
            .filter(event=event, id__in=seat_ids)
            .order_by("id")
        )

        if len(seats) != len(seat_ids):
            raise SeatsUnavailable("Um ou mais assentos selecionados não existem para este evento.")

        seat_pks = [seat.id for seat in seats]
        ticket_by_seat_id = {t.seat_id: t for t in Ticket.objects.filter(seat_id__in=seat_pks)}
        reservation_status_by_id = dict(
            Reservation.objects.filter(
                id__in=[seat.reservation_id for seat in seats if seat.reservation_id]
            ).values_list("id", "status")
        )

        taken = []
        for seat in seats:
            ticket = ticket_by_seat_id.get(seat.id)
            if ticket and ticket.status != Ticket.Status.CANCELED:
                taken.append(seat.label)
                continue
            if (
                seat.reservation_id
                and reservation_status_by_id.get(seat.reservation_id) == Reservation.Status.PENDING
                and seat.held_until
                and seat.held_until > now
            ):
                taken.append(seat.label)

        if taken:
            raise SeatsUnavailable(
                f"Assento(s) {', '.join(taken)} acabaram de ser reservados por outra pessoa."
            )

        reservation.save()
        held_until = now + timedelta(minutes=SEAT_HOLD_MINUTES)
        for seat in seats:
            seat.reservation = reservation
            seat.held_until = held_until
        Seat.objects.bulk_update(seats, ["reservation", "held_until"])

    return reservation
