"""Reddit source using RSS feeds (no auth, no rate-limit blocks).

Reddit RSS endpoints are public and don't trigger the aggressive bot detection
that the JSON API uses. We search across r/all and relevant subreddits.
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

logger = logging.getLogger("signalgraph.pipeline")

ATOM_NS = "http://www.w3.org/2005/Atom"
MEDIA_NS = "http://search.yahoo.com/mrss/"

DEFAULT_SUBREDDITS = [
    "technology",
    "cordcutters",
    "streaming",
    "television",
    "movies",
    "entertainment",
    "appletv",
    "fireTV",
    "roku",
    "AndroidTV",
    "netflix",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


class RedditSource:
    name = "reddit"

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        subreddits: list[str] | None = None,
    ) -> None:
        self._subreddits = subreddits or DEFAULT_SUBREDDITS

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []
        seen_ids: set[str] = set()
        term = search_terms[0] if search_terms else ""
        if not term:
            return mentions

        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=15.0
        ) as client:
            # Search r/all via RSS
            results = await self._fetch_rss(
                client,
                f"https://www.reddit.com/search.rss?q={term}&sort=new&t=month&limit=100",
                since,
            )
            for m in results:
                if m.source_id not in seen_ids:
                    seen_ids.add(m.source_id)
                    mentions.append(m)
            logger.info(f"[reddit] r/all search: {len(results)} posts")
            await asyncio.sleep(1.0)

            # Search specific subreddits
            for sub in self._subreddits:
                url = f"https://www.reddit.com/r/{sub}/search.rss?q={term}&restrict_sr=on&sort=new&t=month&limit=100"
                results = await self._fetch_rss(client, url, since)
                new = 0
                for m in results:
                    if m.source_id not in seen_ids:
                        seen_ids.add(m.source_id)
                        mentions.append(m)
                        new += 1
                if new:
                    logger.info(f"[reddit] r/{sub}: {new} new posts")
                await asyncio.sleep(1.0)

            # Also get recent posts from the dedicated subreddit if it exists
            url = f"https://www.reddit.com/r/{term.lower()}/new.rss?limit=100"
            results = await self._fetch_rss(client, url, since)
            new = 0
            for m in results:
                if m.source_id not in seen_ids:
                    seen_ids.add(m.source_id)
                    mentions.append(m)
                    new += 1
            if new:
                logger.info(f"[reddit] r/{term.lower()} new: {new} posts")

        logger.info(f"[reddit] Total: {len(mentions)} mentions")
        return mentions

    async def _fetch_rss(
        self, client: httpx.AsyncClient, url: str, since: datetime
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []

        try:
            response = await client.get(url)
            if response.status_code != 200:
                logger.warning(f"[reddit] RSS {response.status_code} for {url[:80]}")
                return mentions
            xml_text = response.text
        except Exception as e:
            logger.warning(f"[reddit] RSS fetch error: {e}")
            return mentions

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return mentions

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            try:
                m = self._parse_entry(entry, since)
                if m:
                    mentions.append(m)
            except Exception:
                continue

        return mentions

    def _parse_entry(self, entry, since: datetime) -> RawMentionData | None:
        # Extract fields from Atom entry
        id_el = entry.find(f"{{{ATOM_NS}}}id")
        entry_id = id_el.text.strip() if id_el is not None and id_el.text else ""

        title_el = entry.find(f"{{{ATOM_NS}}}title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        content_el = entry.find(f"{{{ATOM_NS}}}content")
        content = content_el.text.strip() if content_el is not None and content_el.text else ""

        # Parse date
        updated_el = entry.find(f"{{{ATOM_NS}}}updated")
        if updated_el is not None and updated_el.text:
            try:
                published_at = datetime.fromisoformat(
                    updated_el.text.replace("Z", "+00:00")
                )
            except ValueError:
                published_at = datetime.now(tz=timezone.utc)
        else:
            published_at = datetime.now(tz=timezone.utc)

        if published_at < since:
            return None

        # Author
        author_el = entry.find(f"{{{ATOM_NS}}}author")
        author = None
        if author_el is not None:
            name_el = author_el.find(f"{{{ATOM_NS}}}name")
            if name_el is not None and name_el.text:
                author = name_el.text.strip().replace("/u/", "")

        # Link
        link_el = entry.find(f"{{{ATOM_NS}}}link")
        url = link_el.get("href", "") if link_el is not None else ""

        # Category (subreddit)
        cat_el = entry.find(f"{{{ATOM_NS}}}category")
        subreddit = cat_el.get("term", "").strip() if cat_el is not None else ""

        # Build text from title + content (strip HTML from content)
        import re
        clean_content = re.sub(r"<[^>]+>", " ", content)
        clean_content = re.sub(r"\s+", " ", clean_content).strip()

        text = f"{title}\n{clean_content}".strip() if clean_content else title
        if not text or len(text) < 10:
            return None

        # Generate a stable source_id from the entry ID or URL
        source_id = entry_id or url or f"reddit_{hash(text)}"

        return RawMentionData(
            source="reddit",
            source_id=source_id,
            text=text,
            published_at=published_at,
            author=author,
            author_metadata={
                "subreddit": subreddit,
                "type": "post",
            },
            url=url,
            raw_data={
                "title": title,
                "content": clean_content[:1000],
                "subreddit": subreddit,
            },
        )
