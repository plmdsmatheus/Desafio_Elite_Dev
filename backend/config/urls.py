from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.events.views import OrganizerEventListView


def health(request):
    """Unauthenticated, no DB hit — just proves the process is up. Used as
    the health check path by the hosting platform (e.g. Render)."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/events/", include("apps.events.urls")),
    path("api/organizer/events", OrganizerEventListView.as_view(), name="organizer-events"),
    path("api/", include("apps.ticketing.urls")),
]
