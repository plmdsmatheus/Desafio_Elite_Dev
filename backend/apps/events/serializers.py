from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    """Read — public for published events, and for the owning organizer to see their own."""

    tickets_sold = serializers.ReadOnlyField()
    tickets_available = serializers.ReadOnlyField()
    effective_status = serializers.ReadOnlyField()
    # Display name only — never the organizer's e-mail (see EventSerializer
    # history: organizer_email was removed for leaking PII on a public endpoint).
    organizer_name = serializers.CharField(source="organizer.first_name", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "organizer",
            "organizer_name",
            "source_provider",
            "source_id",
            "title",
            "description",
            "image_url",
            "category",
            "venue_name",
            "address",
            "city",
            "date_time",
            "capacity",
            "price",
            "status",
            "effective_status",
            "has_seat_map",
            "tickets_sold",
            "tickets_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organizer", "created_at", "updated_at"]


class EventWriteSerializer(serializers.ModelSerializer):
    """Creation/editing by the organizer.

    Enforces the event lifecycle as a real state machine, not just a free
    `status` field: draft -> published -> canceled, one-directional, with
    published locking down everything except date/time and location. Every
    other view in this codebase already treats `status` (not
    `effective_status`) as the thing that gates behavior — this keeps that
    same convention; "realizado" stays a pure display label computed
    elsewhere, never a new permission gate here."""

    # Fields still open once an event is published — location and timing can
    # change (a venue falls through, a start time slips), everything else
    # (price, capacity, seat map, category...) is locked in at that point.
    PUBLISHED_EDITABLE_FIELDS = {"date_time", "venue_name", "address", "city", "status"}

    class Meta:
        model = Event
        fields = [
            "source_provider",
            "source_id",
            "title",
            "description",
            "image_url",
            "category",
            "venue_name",
            "address",
            "city",
            "date_time",
            "capacity",
            "price",
            "status",
            "has_seat_map",
        ]

    def validate_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Capacidade precisa ser pelo menos 1.")
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Preço não pode ser negativo.")
        return value

    def validate(self, attrs):
        if self.instance is None:
            # Every new event starts as a draft — publishing is a deliberate,
            # separate action, never a value picked at creation time.
            attrs["status"] = Event.Status.DRAFT
            return attrs

        current_status = self.instance.status
        new_status = attrs.get("status", current_status)

        if current_status == Event.Status.CANCELED:
            raise serializers.ValidationError(
                "Um evento cancelado não pode mais ser alterado."
            )

        if current_status == Event.Status.PUBLISHED:
            disallowed = set(attrs) - self.PUBLISHED_EDITABLE_FIELDS
            if disallowed:
                raise serializers.ValidationError(
                    {
                        field: "Não é possível alterar depois que o evento foi publicado — "
                        "só data/hora, local (endereço/cidade) ou cancelamento."
                        for field in disallowed
                    }
                )
            if new_status != current_status and new_status != Event.Status.CANCELED:
                raise serializers.ValidationError(
                    {"status": "Um evento publicado só pode ser cancelado, não voltar a rascunho."}
                )

        if current_status == Event.Status.DRAFT:
            if new_status not in (Event.Status.DRAFT, Event.Status.PUBLISHED):
                raise serializers.ValidationError(
                    {"status": "Um rascunho só pode ser publicado."}
                )

        return attrs
