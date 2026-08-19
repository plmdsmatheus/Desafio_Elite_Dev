from dataclasses import dataclass
from datetime import datetime


class CatalogProviderError(Exception):
    """Erro de configuração/uso do provider (chave ausente, provider desconhecido)."""


@dataclass
class CatalogItem:
    """Resultado de busca no catálogo externo, normalizado entre providers.

    Vira um *snapshot* pré-preenchido no formulário de criação de evento — o
    organizador ainda edita tudo antes de publicar, então os campos "suggested_*"
    são só sugestões, não uma referência viva à API externa.
    """

    provider: str
    external_id: str
    title: str
    category: str  # "show" | "movie" — mesmos valores de Event.Category
    image_url: str = ""
    description: str = ""
    subtitle: str = ""
    suggested_venue_name: str = ""
    suggested_address: str = ""
    suggested_city: str = ""
    suggested_date_time: datetime | None = None


class CatalogProvider:
    key: str

    def search(self, query: str) -> list[CatalogItem]:
        raise NotImplementedError
