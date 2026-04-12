from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class RawMentionData:
    source: str
    source_id: str
    text: str
    published_at: datetime
    author: str | None = None
    author_metadata: dict | None = None
    url: str | None = None
    language: str = "en"
    raw_data: dict = field(default_factory=dict)


class Source(Protocol):
    name: str

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]: ...
