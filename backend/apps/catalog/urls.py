from django.urls import path

from .views import CatalogSearchView

app_name = "catalog"

urlpatterns = [
    path("search", CatalogSearchView.as_view(), name="search"),
]
