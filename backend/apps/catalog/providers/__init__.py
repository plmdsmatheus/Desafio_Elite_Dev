from .base import CatalogItem, CatalogProvider, CatalogProviderError
from .ticketmaster import TicketmasterProvider
from .tmdb import TMDbProvider

PROVIDERS: dict[str, CatalogProvider] = {
    TicketmasterProvider.key: TicketmasterProvider(),
    TMDbProvider.key: TMDbProvider(),
}


def get_provider(key: str) -> CatalogProvider:
    try:
        return PROVIDERS[key]
    except KeyError:
        raise CatalogProviderError(
            f"Provider desconhecido: '{key}'. Use 'ticketmaster' ou 'tmdb'."
        )


__all__ = [
    "CatalogItem",
    "CatalogProvider",
    "CatalogProviderError",
    "PROVIDERS",
    "get_provider",
]
