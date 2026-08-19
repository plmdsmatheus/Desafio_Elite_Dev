from django.conf import settings
from django.db import models


# Module level (instead of nested in the class) so drf-spectacular
# (ENUM_NAME_OVERRIDES) can import each choices directly; the
# Event.SourceProvider/Category/Status aliases below keep the rest of the code reading naturally.
class EventSourceProvider(models.TextChoices):
    TICKETMASTER = "ticketmaster", "Ticketmaster"
    TMDB = "tmdb", "TMDb"
    MANUAL = "manual", "Manual"


class EventCategory(models.TextChoices):
    SHOW = "show", "Show"
    MOVIE = "movie", "Filme"


class EventStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    PUBLISHED = "published", "Publicado"
    CANCELED = "canceled", "Cancelado"


class EventQuerySet(models.QuerySet):
    def with_sold_counts(self):
        """Annotates _sold_count so tickets_sold/tickets_available don't each run
        their own query per row — without this, listing N events costs 2N extra
        SUM queries (Event.tickets_sold below falls back to that per-instance
        query when the annotation isn't present, e.g. after a plain .get())."""
        from apps.ticketing.models import ReservationStatus

        return self.annotate(
            _sold_count=models.Sum(
                "reservations__quantity",
                filter=models.Q(reservations__status=ReservationStatus.PAID),
            )
        ).order_by("date_time")  # annotate()'s GROUP BY can drop the Meta.ordering default


class Event(models.Model):
    SourceProvider = EventSourceProvider
    Category = EventCategory
    Status = EventStatus

    objects = EventQuerySet.as_manager()

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
        limit_choices_to={"role": "organizer"},
    )

    # Snapshot of the item picked from the external catalog — not a live reference:
    # the organizer freely edits date/venue/capacity/price after picking it.
    source_provider = models.CharField(
        max_length=20, choices=SourceProvider.choices, default=SourceProvider.MANUAL
    )
    source_id = models.CharField(max_length=255, blank=True)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    category = models.CharField(max_length=10, choices=Category.choices)

    venue_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)

    date_time = models.DateTimeField()
    capacity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date_time"]

    def __str__(self):
        return f"{self.title} ({self.date_time:%d/%m/%Y})"

    @property
    def tickets_sold(self) -> int:
        """Quantity already sold (paid reservations). Uses the with_sold_counts()
        annotation when available (list views); otherwise falls back to a
        one-off query (single-instance use, e.g. inside the payment lock).
        Local import to avoid a module-level dependency between events and
        ticketing when the apps load."""
        annotated = getattr(self, "_sold_count", None)
        if annotated is not None:
            return annotated

        from apps.ticketing.models import Reservation

        total = self.reservations.filter(status=Reservation.Status.PAID).aggregate(
            total=models.Sum("quantity")
        )["total"]
        return total or 0

    @property
    def tickets_available(self) -> int:
        return max(self.capacity - self.tickets_sold, 0)
