from django.urls import path

from .views import EventCityListView, EventDetailView, EventListCreateView

app_name = "events"

urlpatterns = [
    path("", EventListCreateView.as_view(), name="list-create"),
    path("cities", EventCityListView.as_view(), name="cities"),
    path("<int:pk>", EventDetailView.as_view(), name="detail"),
]
