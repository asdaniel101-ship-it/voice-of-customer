import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

logger = logging.getLogger("signalgraph.pipeline")

ATOM_NS = "http://www.w3.org/2005/Atom"
ITUNES_NS = "http://itunes.apple.com/rss"

RSS_URL_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/xml"
)

JSON_URL_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortBy=mostRecent/json"
)


class AppStoreSource:
    name = "appstore"

    COUNTRIES = ["us", "gb", "ca", "au", "in"]

    def __init__(self, app_id: str, country: str = "us") -> None:
        self._app_id = app_id
        self._country = country

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        all_mentions: list[RawMentionData] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            for country in self.COUNTRIES:
                # Try paginated JSON feed first (more reliable), then XML fallback
                country_mentions = await self._fetch_country_json(client, country)
                if not country_mentions:
                    country_mentions = await self._fetch_country_xml(client, country)
                logger.info(f"[appstore] {country}: {len(country_mentions)} reviews")
                all_mentions.extend(country_mentions)

        return all_mentions

    async def _fetch_country_json(
        self, client: httpx.AsyncClient, country: str
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []

        for page in range(1, 11):  # Up to 10 pages
            url = JSON_URL_TEMPLATE.format(
                country=country, page=page, app_id=self._app_id
            )
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    break
                data = response.json()
                entries = data.get("feed", {}).get("entry", [])
                if not entries:
                    break

                for entry in entries:
                    # Skip the app metadata entry (first entry is app info)
                    if "im:rating" not in entry:
                        continue

                    title = entry.get("title", {}).get("label", "")
                    content = entry.get("content", {}).get("label", "")
                    author = entry.get("author", {}).get("name", {}).get("label")
                    entry_id = entry.get("id", {}).get("label", "")

                    rating = None
                    rating_val = entry.get("im:rating", {}).get("label")
                    if rating_val:
                        try:
                            rating = int(rating_val)
                        except ValueError:
                            pass

                    version = entry.get("im:version", {}).get("label")

                    # Parse date
                    published_at = datetime.now(tz=timezone.utc)

                    text_parts = [p for p in [title, content] if p]
                    text = "\n".join(text_parts) if text_parts else ""
                    if not text:
                        continue

                    mentions.append(RawMentionData(
                        source="appstore",
                        source_id=entry_id or f"{self._app_id}_{country}_{len(mentions)}",
                        text=text,
                        published_at=published_at,
                        author=author,
                        author_metadata={
                            "rating": rating,
                            "version": version,
                            "app_id": self._app_id,
                            "country": country,
                        },
                        raw_data={
                            "id": entry_id,
                            "title": title,
                            "content": content,
                            "rating": rating,
                            "version": version,
                        },
                    ))

            except Exception:
                break

        return mentions

    async def _fetch_country_xml(
        self, client: httpx.AsyncClient, country: str
    ) -> list[RawMentionData]:
        url = RSS_URL_TEMPLATE.format(country=country, app_id=self._app_id)

        try:
            response = await client.get(url)
            response.raise_for_status()
            xml_content = response.text
        except Exception:
            return []

        root = ET.fromstring(xml_content)

        mentions: list[RawMentionData] = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
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

            updated_el = entry.find(f"{{{ATOM_NS}}}updated")
            published_at = datetime.now(tz=timezone.utc)
            if updated_el is not None and updated_el.text:
                try:
                    published_at = datetime.fromisoformat(
                        updated_el.text.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            rating_el = entry.find(f"{{{ITUNES_NS}}}rating")
            rating = None
            if rating_el is not None and rating_el.text:
                try:
                    rating = int(rating_el.text)
                except ValueError:
                    pass

            version_el = entry.find(f"{{{ITUNES_NS}}}version")
            version = version_el.text if version_el is not None else None

            text_parts = [p for p in [title, content] if p]
            text = "\n".join(text_parts) if text_parts else ""

            mentions.append(RawMentionData(
                source="appstore",
                source_id=entry_id or f"{self._app_id}_{len(mentions)}",
                text=text,
                published_at=published_at,
                author=author_name,
                author_metadata={
                    "rating": rating,
                    "version": version,
                    "app_id": self._app_id,
                    "country": country,
                },
                raw_data={
                    "id": entry_id,
                    "title": title,
                    "content": content,
                    "rating": rating,
                    "version": version,
                },
            ))

        return mentions
