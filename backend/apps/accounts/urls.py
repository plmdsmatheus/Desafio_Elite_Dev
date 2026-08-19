from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, MeView, RegisterView

app_name = "accounts"

TaggedTokenRefreshView = extend_schema(tags=["auth"])(TokenRefreshView)

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("refresh", TaggedTokenRefreshView.as_view(), name="refresh"),
    path("me", MeView.as_view(), name="me"),
]
