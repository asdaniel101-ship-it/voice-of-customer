import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

ATOM_NS = "http://www.w3.org/2005/Atom"
ITUNES_NS = "http://itunes.apple.com/rss"

RSS_URL_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/xml"
)


class AppStoreSource:
    name = "appstore"

    def __init__(self, app_id: str, country: str = "us") -> None:
        self._app_id = app_id
        self._country = country

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        url = RSS_URL_TEMPLATE.format(country=self._country, app_id=self._app_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            xml_content = response.text

        root = ET.fromstring(xml_content)

        mentions: list[RawMentionData] = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            # Extract basic fields
            entry_id_el = entry.find(f"{{{ATOM_NS}}}id")
            entry_id = entry_id_el.text if entry_id_el is not None else ""

            title_el = entry.find(f"{{{ATOM_NS}}}title")
            title = title_el.text if title_el is not None else ""

            content_el = entry.find(f"{{{ATOM_NS}}}content")
            content = content_el.text if content_el is not None else ""

            author_el = entry.find(f"{{{ATOM_NS}}}author")
            author_name = None
            if author_el is not None:
                author_name_el = author_el.find(f"{{{ATOM_NS}}}name")
                if author_name_el is not None:
                    author_name = author_name_el.text

            # Updated date
            updated_el = entry.find(f"{{{ATOM_NS}}}updated")
            published_at = datetime.now(tz=timezone.utc)
            if updated_el is not None and updated_el.text:
                try:
                    published_at = datetime.fromisoformat(
                        updated_el.text.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # iTunes-specific fields
            rating_el = entry.find(f"{{{ITUNES_NS}}}rating")
            rating = None
            if rating_el is not None and rating_el.text:
                try:
                    rating = int(rating_el.text)
                except ValueError:
                    pass

            version_el = entry.find(f"{{{ITUNES_NS}}}version")
            version = version_el.text if version_el is not None else None

            # Combine title and content
            text_parts = [p for p in [title, content] if p]
            text = "\n".join(text_parts) if text_parts else ""

            mention = RawMentionData(
                source="appstore",
                source_id=entry_id or f"{self._app_id}_{len(mentions)}",
                text=text,
                published_at=published_at,
                author=author_name,
                author_metadata={
                    "rating": rating,
                    "version": version,
                    "app_id": self._app_id,
                    "country": self._country,
                },
                raw_data={
                    "id": entry_id,
                    "title": title,
                    "content": content,
                    "rating": rating,
                    "version": version,
                },
            )
            mentions.append(mention)

        return mentions
