from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsSource:
    name = "hackernews"

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        query = " OR ".join(search_terms)
        since_ts = int(since.timestamp())

        async with httpx.AsyncClient() as client:
            response = await client.get(
                HN_SEARCH_URL,
                params={
                    "query": query,
                    "numericFilters": f"created_at_i>{since_ts}",
                    "tags": "(story,comment)",
                    "hitsPerPage": 100,
                },
            )
            response.raise_for_status()
            data = response.json()

        mentions: list[RawMentionData] = []
        for hit in data.get("hits", []):
            created_at_i = hit.get("created_at_i", 0)
            published_at = datetime.fromtimestamp(created_at_i, tz=timezone.utc)

            # Stories have title + text; comments have comment_text
            title = hit.get("title", "")
            story_text = hit.get("story_text") or hit.get("comment_text") or ""
            text = f"{title}\n{story_text}".strip() if story_text else title

            object_id = hit.get("objectID", "")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"

            mention = RawMentionData(
                source="hackernews",
                source_id=object_id,
                text=text,
                published_at=published_at,
                author=hit.get("author"),
                author_metadata={
                    "points": hit.get("points"),
                    "num_comments": hit.get("num_comments"),
                    "story_id": hit.get("story_id"),
                    "type": hit.get("_tags", [None])[0] if hit.get("_tags") else None,
                },
                url=url,
                raw_data=hit,
            )
            mentions.append(mention)

        return mentions
