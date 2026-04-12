from datetime import datetime

from signalgraph.sources.base import RawMentionData


class WebSearchSource:
    name = "websearch"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        # Stub: Web search integration requires a search API (e.g., SerpAPI, Bing, Google CSE).
        return []
