from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    """Leitura — pública para eventos publicados, e para o organizador dono ver os próprios."""

    tickets_sold = serializers.ReadOnlyField()
    tickets_available = serializers.ReadOnlyField()
    organizer_email = serializers.EmailField(source="organizer.email", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "organizer",
            "organizer_email",
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
            "tickets_sold",
            "tickets_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organizer", "created_at", "updated_at"]


class EventWriteSerializer(serializers.ModelSerializer):
    """Criação/edição pelo organizador."""

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
        capacity = attrs.get("capacity")
        if self.instance and capacity is not None and capacity < self.instance.tickets_sold:
            raise serializers.ValidationError(
                {
                    "capacity": (
                        "Não é possível reduzir a capacidade abaixo da quantidade já vendida "
                        f"({self.instance.tickets_sold})."
                    )
                }
            )
        return attrs
