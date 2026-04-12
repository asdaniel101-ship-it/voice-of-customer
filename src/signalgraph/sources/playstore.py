from datetime import datetime

from signalgraph.sources.base import RawMentionData


class PlayStoreSource:
    name = "playstore"

    def __init__(self, app_id: str, country: str = "us") -> None:
        self._app_id = app_id
        self._country = country

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        # Stub: Play Store scraping requires unofficial APIs or third-party services.
        return []
