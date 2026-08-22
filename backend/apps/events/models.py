from django.conf import settings
from django.db import models
from django.utils import timezone


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


class EventAgeRating(models.TextChoices):
    """Same codes as ANCINE's classificação indicativa — also what TMDb's
    release_dates certification field for BR already returns as-is."""

    FREE = "L", "Livre"
    TEN = "10", "10 anos"
    TWELVE = "12", "12 anos"
    FOURTEEN = "14", "14 anos"
    SIXTEEN = "16", "16 anos"
    EIGHTEEN = "18", "18 anos"


class EventQuerySet(models.QuerySet):
    def with_sold_counts(self):
        """Annotates _sold_count so tickets_sold/tickets_available don't each run
        their own query per row — without this, listing N events costs 2N extra
        COUNT queries (Event.tickets_sold below falls back to that per-instance
        query when the annotation isn't present, e.g. after a plain .get()).

        Counts actual non-canceled Tickets rather than summing paid reservation
        quantities: a reservation's quantity is fixed at purchase time, but
        individual tickets can later be canceled and returned to stock (see
        TicketCancelView) without changing the reservation itself."""
        from apps.ticketing.models import TicketStatus

        return self.annotate(
            _sold_count=models.Count(
                "tickets", filter=~models.Q(tickets__status=TicketStatus.CANCELED), distinct=True
            )
        ).order_by("date_time")  # annotate()'s GROUP BY can drop the Meta.ordering default


class Event(models.Model):
    SourceProvider = EventSourceProvider
    Category = EventCategory
    Status = EventStatus
    AgeRating = EventAgeRating

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
    # Blank = unknown/not set — nothing shown, not "Livre". Only ever comes
    # from a real source: the organizer picking it manually or a catalog
    # search result that actually had the data (see apps.catalog.providers).
    age_rating = models.CharField(max_length=3, choices=AgeRating.choices, blank=True, default="")

    venue_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)

    date_time = models.DateTimeField()
    capacity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # Assigned seating (cinema/theater) instead of general-admission quantity.
    # Seats are (re)generated from `capacity` — see apps.ticketing.seating.
    has_seat_map = models.BooleanField(default=False)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date_time"]

    def __str__(self):
        return f"{self.title} ({self.date_time:%d/%m/%Y})"

    @property
    def tickets_sold(self) -> int:
        """Tickets currently held against capacity (valid + used, excluding
        canceled). Uses the with_sold_counts() annotation when available (list
        views); otherwise falls back to a one-off query (single-instance use,
        e.g. inside the payment lock). Local import to avoid a module-level
        dependency between events and ticketing when the apps load."""
        annotated = getattr(self, "_sold_count", None)
        if annotated is not None:
            return annotated

        from apps.ticketing.models import TicketStatus

        return self.tickets.exclude(status=TicketStatus.CANCELED).count()

    @property
    def tickets_available(self) -> int:
        return max(self.capacity - self.tickets_sold, 0)

    @property
    def effective_status(self) -> str:
        """`status` reflects organizer intent (draft/published/canceled) and
        is never auto-changed — there's no scheduled job in this project to
        flip it. This is a purely computed display label layered on top: a
        published event whose date has already passed reads as "completed"
        everywhere (organizer panel, detail page) without needing a cron."""
        if self.status == self.Status.PUBLISHED and self.date_time <= timezone.now():
            return "completed"
        return self.status
