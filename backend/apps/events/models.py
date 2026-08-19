from django.conf import settings
from django.db import models


class Event(models.Model):
    class SourceProvider(models.TextChoices):
        TICKETMASTER = "ticketmaster", "Ticketmaster"
        TMDB = "tmdb", "TMDb"
        MANUAL = "manual", "Manual"

    class Category(models.TextChoices):
        SHOW = "show", "Show"
        MOVIE = "movie", "Filme"

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        PUBLISHED = "published", "Publicado"
        CANCELED = "canceled", "Cancelado"

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
        limit_choices_to={"role": "organizer"},
    )

    # Snapshot do item escolhido no catálogo externo — não é uma referência viva:
    # o organizador edita data/local/capacidade/preço livremente depois de escolher.
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
    def tickets_sold(self):
        """Quantidade já vendida (reservas pagas). Import local para não criar
        dependência de módulo entre events e ticketing na hora de carregar as apps."""
        from apps.ticketing.models import Reservation

        total = self.reservations.filter(status=Reservation.Status.PAID).aggregate(
            total=models.Sum("quantity")
        )["total"]
        return total or 0

    @property
    def tickets_available(self):
        return max(self.capacity - self.tickets_sold, 0)
