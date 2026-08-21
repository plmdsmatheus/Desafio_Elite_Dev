from datetime import datetime

import requests
from django.conf import settings

from .base import CatalogItem, CatalogProvider, CatalogProviderError

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class TMDbProvider(CatalogProvider):
    """https://developer.themoviedb.org/docs/search-and-query-for-details"""

    key = "tmdb"
    base_url = "https://api.themoviedb.org/3/search/movie"

    def search(self, query: str) -> list[CatalogItem]:
        headers = {}
        params = {"query": query, "language": "pt-BR", "include_adult": "false"}

        if settings.TMDB_API_READ_ACCESS_TOKEN:
            headers["Authorization"] = f"Bearer {settings.TMDB_API_READ_ACCESS_TOKEN}"
        elif settings.TMDB_API_KEY:
            params["api_key"] = settings.TMDB_API_KEY
        else:
            raise CatalogProviderError(
                "TMDB_API_KEY ou TMDB_API_READ_ACCESS_TOKEN não configurados no .env."
            )

        response = requests.get(self.base_url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        results = response.json().get("results", [])
        return [self._to_item(movie) for movie in results]

    def _to_item(self, movie: dict) -> CatalogItem:
        image_url = f"{TMDB_IMAGE_BASE}{movie['poster_path']}" if movie.get("poster_path") else ""

        date_time = None
        if movie.get("release_date"):
            date_time = datetime.strptime(movie["release_date"], "%Y-%m-%d")

        return CatalogItem(
            provider=self.key,
            external_id=str(movie["id"]),
            title=movie.get("title", ""),
            category="movie",
            image_url=image_url,
            description=movie.get("overview", "") or "",
            suggested_date_time=date_time,
        )
