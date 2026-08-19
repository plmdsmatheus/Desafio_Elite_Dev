from django.contrib import admin
from django.urls import include, path

from apps.events.views import OrganizerEventListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/events/", include("apps.events.urls")),
    path("api/organizer/events", OrganizerEventListView.as_view(), name="organizer-events"),
    path("api/", include("apps.ticketing.urls")),
]
