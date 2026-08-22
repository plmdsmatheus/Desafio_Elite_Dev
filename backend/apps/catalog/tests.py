from unittest.mock import MagicMock, patch

import pytest
from requests import RequestException

from apps.catalog.providers import CatalogProviderError, get_provider
from apps.catalog.providers.base import CatalogItem
from apps.catalog.providers.ticketmaster import TicketmasterProvider
from apps.catalog.providers.tmdb import TMDbProvider


class TestProviderParsing:
    """Parsing of payloads in the real API format — no network calls."""

    def test_ticketmaster_maps_full_event(self):
        item = TicketmasterProvider()._to_item(
            {
                "id": "abc123",
                "name": "Show de Teste",
                "images": [
                    {"width": 200, "url": "http://x/small.jpg"},
                    {"width": 1024, "url": "http://x/large.jpg"},
                ],
                "info": "Info geral",
                "dates": {"start": {"dateTime": "2026-09-15T23:00:00Z"}},
                "classifications": [{"segment": {"name": "Music"}, "genre": {"name": "Rock"}}],
                "_embedded": {
                    "venues": [
                        {
                            "name": "Allianz Parque",
                            "city": {"name": "São Paulo"},
                            "address": {"line1": "Av. Palestra Italia, 1"},
                        }
                    ]
                },
            }
        )

        assert item.provider == "ticketmaster"
        assert item.external_id == "abc123"
        assert item.title == "Show de Teste"
        assert item.category == "show"
        assert item.image_url == "http://x/large.jpg"
        assert item.description == "Info geral"
        assert item.subtitle == "Music · Rock"
        assert item.suggested_venue_name == "Allianz Parque"
        assert item.suggested_address == "Av. Palestra Italia, 1"
        assert item.suggested_city == "São Paulo"
        assert item.suggested_date_time.isoformat() == "2026-09-15T23:00:00+00:00"
        assert item.suggested_age_rating == ""

    def test_ticketmaster_handles_missing_fields_without_crashing(self):
        item = TicketmasterProvider()._to_item({"id": "x1", "name": "Sem frescura", "dates": {"start": {}}})
        assert item.image_url == ""
        assert item.suggested_venue_name == ""
        assert item.suggested_date_time is None

    def test_ticketmaster_maps_age_restriction_to_18(self):
        item = TicketmasterProvider()._to_item(
            {"id": "x2", "name": "Show +18", "dates": {"start": {}}, "ageRestrictions": {"legalAgeEnforced": True}}
        )
        assert item.suggested_age_rating == "18"

    def test_tmdb_maps_full_movie(self):
        item = TMDbProvider()._to_item(
            {
                "id": 550,
                "title": "Clube da Luta",
                "overview": "Uma descrição",
                "poster_path": "/abc123.jpg",
                "release_date": "1999-10-15",
            }
        )
        assert item.provider == "tmdb"
        assert item.external_id == "550"
        assert item.category == "movie"
        assert item.image_url == "https://image.tmdb.org/t/p/w500/abc123.jpg"
        assert item.suggested_date_time.isoformat() == "1999-10-15T00:00:00"

    def test_tmdb_handles_missing_poster(self):
        item = TMDbProvider()._to_item({"id": 1, "title": "Sem poster"})
        assert item.image_url == ""
        assert item.suggested_date_time is None

    def test_tmdb_maps_age_rating_when_passed(self):
        item = TMDbProvider()._to_item({"id": 1, "title": "Com classificação"}, age_rating="14")
        assert item.suggested_age_rating == "14"


class TestTMDbCertification:
    """`_fetch_br_certification` / the parallel fetch in `search()` — no network calls."""

    def test_prefers_theatrical_release_over_others(self):
        response_json = {
            "results": [
                {
                    "iso_3166_1": "BR",
                    "release_dates": [
                        {"type": 4, "certification": "12"},
                        {"type": 3, "certification": "14"},
                    ],
                },
                {"iso_3166_1": "US", "release_dates": [{"type": 3, "certification": "PG-13"}]},
            ]
        }
        with patch("apps.catalog.providers.tmdb.requests.get") as mock_get:
            mock_get.return_value.json.return_value = response_json
            mock_get.return_value.raise_for_status.return_value = None
            cert = TMDbProvider()._fetch_br_certification(550, headers={}, auth_params={})
        assert cert == "14"

    def test_no_br_entry_returns_blank(self):
        with patch("apps.catalog.providers.tmdb.requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"results": [{"iso_3166_1": "US", "release_dates": []}]}
            mock_get.return_value.raise_for_status.return_value = None
            cert = TMDbProvider()._fetch_br_certification(1, headers={}, auth_params={})
        assert cert == ""

    def test_request_failure_returns_blank_not_raises(self):
        with patch("apps.catalog.providers.tmdb.requests.get", side_effect=RequestException("boom")):
            cert = TMDbProvider()._fetch_br_certification(1, headers={}, auth_params={})
        assert cert == ""

    def test_search_attaches_certification_per_movie(self):
        search_response = {"results": [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]}

        def fake_get(url, params=None, headers=None, timeout=None):
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            if "release_dates" in url:
                movie_id = int(url.split("/")[-2])
                cert = "16" if movie_id == 1 else ""
                mock_response.json.return_value = {
                    "results": [{"iso_3166_1": "BR", "release_dates": [{"type": 3, "certification": cert}]}]
                    if cert
                    else []
                }
            else:
                mock_response.json.return_value = search_response
            return mock_response

        with patch("apps.catalog.providers.tmdb.settings.TMDB_API_READ_ACCESS_TOKEN", "fake-token"):
            with patch("apps.catalog.providers.tmdb.requests.get", side_effect=fake_get):
                items = TMDbProvider().search("qualquer coisa")

        by_id = {item.external_id: item.suggested_age_rating for item in items}
        assert by_id == {"1": "16", "2": ""}


class TestProviderRegistry:
    def test_get_provider_returns_correct_instance(self):
        assert isinstance(get_provider("ticketmaster"), TicketmasterProvider)
        assert isinstance(get_provider("tmdb"), TMDbProvider)

    def test_get_provider_unknown_key_raises(self):
        with pytest.raises(CatalogProviderError):
            get_provider("netflix")


@pytest.mark.django_db
class TestCatalogSearchView:
    def test_requires_organizer_role(self, api_client, customer):
        api_client.force_authenticate(user=customer)
        response = api_client.get("/api/catalog/search", {"provider": "tmdb", "q": "matrix"})
        assert response.status_code == 403

    def test_requires_query_param(self, api_client, organizer):
        api_client.force_authenticate(user=organizer)
        response = api_client.get("/api/catalog/search", {"provider": "tmdb"})
        assert response.status_code == 400

    def test_unknown_provider_returns_400(self, api_client, organizer):
        api_client.force_authenticate(user=organizer)
        response = api_client.get("/api/catalog/search", {"provider": "netflix", "q": "x"})
        assert response.status_code == 400

    def test_missing_api_key_returns_400_not_500(self, api_client, organizer, settings):
        settings.TICKETMASTER_API_KEY = ""
        api_client.force_authenticate(user=organizer)
        response = api_client.get("/api/catalog/search", {"provider": "ticketmaster", "q": "x"})
        assert response.status_code == 400

    def test_successful_search_returns_serialized_items(self, api_client, organizer):
        api_client.force_authenticate(user=organizer)
        fake_item = CatalogItem(
            provider="tmdb", external_id="1", title="Filme Falso", category="movie"
        )
        with patch.object(TMDbProvider, "search", return_value=[fake_item]):
            response = api_client.get("/api/catalog/search", {"provider": "tmdb", "q": "falso"})

        assert response.status_code == 200
        assert response.data[0]["title"] == "Filme Falso"
