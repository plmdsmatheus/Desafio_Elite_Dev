from django.contrib import admin

from .models import Payment, Reservation, Ticket


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = ("public_code", "share_slug", "status", "used_at")
    can_delete = False


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "customer", "quantity", "status", "total_price", "created_at")
    list_filter = ("status", "event")
    search_fields = ("event__title", "customer__email")
    autocomplete_fields = ("event", "customer")
    inlines = [PaymentInline, TicketInline]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("public_code", "event", "owner", "status", "used_at", "created_at")
    list_filter = ("status", "event")
    search_fields = ("public_code", "owner__email", "event__title")
    readonly_fields = ("public_code", "share_slug")
    autocomplete_fields = ("event", "owner", "reservation")
