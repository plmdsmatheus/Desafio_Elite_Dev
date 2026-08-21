from django.urls import path

from .views import EventDetailView, EventListCreateView

app_name = "events"

urlpatterns = [
    path("", EventListCreateView.as_view(), name="list-create"),
    path("<int:pk>", EventDetailView.as_view(), name="detail"),
]
