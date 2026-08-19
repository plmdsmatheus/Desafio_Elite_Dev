import requests
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOrganizer

from .providers import CatalogProviderError, get_provider
from .serializers import CatalogItemSerializer


class CatalogSearchView(APIView):
    """Proxy de busca no catálogo externo (Ticketmaster/TMDb).

    Só o organizador pode chamar: é aqui que ele escolhe o item que vira a base
    de um novo evento. A chave da API nunca sai do backend.
    """

    permission_classes = [IsOrganizer]

    @extend_schema(
        tags=["catalog"],
        parameters=[
            OpenApiParameter(
                "provider",
                str,
                enum=["ticketmaster", "tmdb"],
                required=True,
                description="Qual catálogo externo consultar.",
            ),
            OpenApiParameter(
                "q", str, required=True, description="Termo de busca (nome do show/artista/filme)."
            ),
        ],
        responses=CatalogItemSerializer(many=True),
    )
    def get(self, request):
        provider_key = request.query_params.get("provider", "")
        query = request.query_params.get("q", "").strip()

        if not query:
            return Response({"detail": "Parâmetro 'q' é obrigatório."}, status=400)

        try:
            provider = get_provider(provider_key)
            items = provider.search(query)
        except CatalogProviderError as exc:
            return Response({"detail": str(exc)}, status=400)
        except requests.RequestException:
            return Response(
                {"detail": "Erro ao consultar o catálogo externo. Tente novamente."},
                status=502,
            )

        serializer = CatalogItemSerializer(items, many=True)
        return Response(serializer.data)
