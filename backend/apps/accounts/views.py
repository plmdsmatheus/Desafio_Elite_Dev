from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import EmailTokenObtainPairSerializer, RegisterSerializer, UserSerializer


@extend_schema(tags=["auth"])
class RegisterView(generics.CreateAPIView):
    """Public signup — always creates a user with the customer role.
    Organizer and gate accounts are provisioned via seed/admin (operational accounts)."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema(tags=["auth"])
class LoginView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["auth"], responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)
