from dataclasses import dataclass
from datetime import datetime


class CatalogProviderError(Exception):
    """Provider configuration/usage error (missing key, unknown provider)."""


@dataclass
class CatalogItem:
    """External catalog search result, normalized across providers.

    Becomes a pre-filled *snapshot* in the event creation form — the organizer
    still edits everything before publishing, so the "suggested_*" fields are
    just suggestions, not a live reference to the external API.
    """

    provider: str
    external_id: str
    title: str
    category: str  # "show" | "movie" — same values as Event.Category
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
