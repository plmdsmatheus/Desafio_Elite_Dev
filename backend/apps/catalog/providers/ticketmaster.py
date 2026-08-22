from datetime import datetime

import requests
from django.conf import settings

from .base import CatalogItem, CatalogProvider, CatalogProviderError


class TicketmasterProvider(CatalogProvider):
    """https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/"""

    key = "ticketmaster"
    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"

    def search(self, query: str) -> list[CatalogItem]:
        if not settings.TICKETMASTER_API_KEY:
            raise CatalogProviderError("TICKETMASTER_API_KEY não configurada no .env.")

        response = requests.get(
            self.base_url,
            params={
                "apikey": settings.TICKETMASTER_API_KEY,
                "keyword": query,
                "locale": "*",
                "size": 20,
            },
            timeout=8,
        )
        response.raise_for_status()
        events = response.json().get("_embedded", {}).get("events", [])
        return [self._to_item(event) for event in events]

    def _to_item(self, event: dict) -> CatalogItem:
        images = event.get("images") or []
        image_url = max(images, key=lambda i: i.get("width", 0))["url"] if images else ""

        venues = event.get("_embedded", {}).get("venues", [])
        venue = venues[0] if venues else {}

        start = event.get("dates", {}).get("start", {})
        date_time = None
        if start.get("dateTime"):
            date_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))

        classifications = event.get("classifications") or []
        subtitle = ""
        if classifications:
            segment = classifications[0].get("segment", {}).get("name", "") or ""
            genre = classifications[0].get("genre", {}).get("name", "") or ""
            subtitle = " · ".join(part for part in (segment, genre) if part and part != "Undefined")

        # Discovery API only ever gives a yes/no flag here, never an actual
        # rating number — "18" is the closest honest mapping, not a guess at
        # which number applies.
        age_rating = "18" if (event.get("ageRestrictions") or {}).get("legalAgeEnforced") else ""

        return CatalogItem(
            provider=self.key,
            external_id=event["id"],
            title=event.get("name", ""),
            category="show",
            image_url=image_url,
            description=event.get("info") or event.get("pleaseNote") or "",
            subtitle=subtitle,
            suggested_venue_name=venue.get("name", "") or "",
            suggested_address=(venue.get("address") or {}).get("line1", "") or "",
            suggested_city=(venue.get("city") or {}).get("name", "") or "",
            suggested_date_time=date_time,
            suggested_age_rating=age_rating,
        )
