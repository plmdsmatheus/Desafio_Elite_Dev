from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organizer",
        "category",
        "city",
        "date_time",
        "capacity",
        "price",
        "status",
    )
    list_filter = ("category", "status", "source_provider", "city")
    search_fields = ("title", "city", "venue_name")
    autocomplete_fields = ("organizer",)
    readonly_fields = ("created_at", "updated_at")
