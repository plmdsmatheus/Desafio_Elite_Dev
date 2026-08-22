import concurrent.futures
from datetime import datetime

import requests
from django.conf import settings

from .base import CatalogItem, CatalogProvider, CatalogProviderError

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_API_BASE = "https://api.themoviedb.org/3"


class TMDbProvider(CatalogProvider):
    """https://developer.themoviedb.org/docs/search-and-query-for-details"""

    key = "tmdb"
    base_url = f"{TMDB_API_BASE}/search/movie"

    def search(self, query: str) -> list[CatalogItem]:
        headers = {}
        auth_params = {}

        if settings.TMDB_API_READ_ACCESS_TOKEN:
            headers["Authorization"] = f"Bearer {settings.TMDB_API_READ_ACCESS_TOKEN}"
        elif settings.TMDB_API_KEY:
            auth_params["api_key"] = settings.TMDB_API_KEY
        else:
            raise CatalogProviderError(
                "TMDB_API_KEY ou TMDB_API_READ_ACCESS_TOKEN não configurados no .env."
            )

        params = {"query": query, "language": "pt-BR", "include_adult": "false", **auth_params}
        response = requests.get(self.base_url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        results = response.json().get("results", [])

        # The search endpoint itself carries no certification — only
        # /movie/{id}/release_dates does, one call per movie. Fetched in
        # parallel (20 results at ~300ms sequentially would make a single
        # search feel broken) and best-effort: a movie with no BR rating on
        # file, or one failed request, just contributes "" instead of
        # failing the whole search.
        certifications: dict[int, str] = {}
        if results:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = {
                    pool.submit(self._fetch_br_certification, movie["id"], headers, auth_params): movie["id"]
                    for movie in results
                }
                for future in concurrent.futures.as_completed(futures):
                    certifications[futures[future]] = future.result()

        return [self._to_item(movie, certifications.get(movie["id"], "")) for movie in results]

    def _fetch_br_certification(self, movie_id: int, headers: dict, auth_params: dict) -> str:
        try:
            response = requests.get(
                f"{TMDB_API_BASE}/movie/{movie_id}/release_dates",
                params=auth_params,
                headers=headers,
                timeout=5,
            )
            response.raise_for_status()
            countries = response.json().get("results", [])
        except (requests.RequestException, ValueError):
            return ""

        for country in countries:
            if country.get("iso_3166_1") != "BR":
                continue
            # A title can carry several BR entries (theatrical, VOD, TV) with
            # different certifications — prefer the theatrical one (type 3).
            release_dates = sorted(
                country.get("release_dates") or [], key=lambda rd: rd.get("type") != 3
            )
            for release_date in release_dates:
                certification = release_date.get("certification")
                if certification:
                    return certification
        return ""

    def _to_item(self, movie: dict, age_rating: str = "") -> CatalogItem:
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
            suggested_age_rating=age_rating,
        )
