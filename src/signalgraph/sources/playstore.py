"""Google Play Store source using google-play-scraper package.

Pulls real app reviews with ratings, timestamps, and author data.
No API key needed.
"""

import asyncio
from datetime import datetime, timezone
from functools import partial

from google_play_scraper import Sort, reviews

from signalgraph.sources.base import RawMentionData


class PlayStoreSource:
    name = "playstore"

    def __init__(self, app_id: str, country: str = "us") -> None:
        self._app_id = app_id
        self._country = country

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []

        # Fetch reviews in multiple sort orders for broader coverage
        for sort_order in [Sort.NEWEST, Sort.MOST_RELEVANT]:
            batch = await self._fetch_reviews(sort_order, since)
            mentions.extend(batch)

        return mentions

    async def _fetch_reviews(
        self, sort: Sort, since: datetime
    ) -> list[RawMentionData]:
        """Fetch reviews using google-play-scraper (runs in thread pool since it's sync)."""
        loop = asyncio.get_event_loop()

        try:
            # google-play-scraper is synchronous, run in executor
            result, _ = await loop.run_in_executor(
                None,
                partial(
                    reviews,
                    self._app_id,
                    lang="en",
                    country=self._country,
                    sort=sort,
                    count=200,
                ),
            )
        except Exception:
            return []

        mentions: list[RawMentionData] = []

        for review in result:
            # Parse timestamp
            review_at = review.get("at")
            if isinstance(review_at, datetime):
                published_at = review_at.replace(tzinfo=timezone.utc)
            else:
                published_at = datetime.now(tz=timezone.utc)

            if published_at < since:
                continue

            text = review.get("content", "")
            if not text or len(text) < 5:
                continue

            review_id = review.get("reviewId", "")
            score = review.get("score", 0)

            mention = RawMentionData(
                source="playstore",
                source_id=review_id,
                text=text,
                published_at=published_at,
                author=review.get("userName"),
                author_metadata={
                    "rating": score,
                    "app_id": self._app_id,
                    "country": self._country,
                    "thumbs_up": review.get("thumbsUpCount", 0),
                    "app_version": review.get("reviewCreatedVersion"),
                },
                url=f"https://play.google.com/store/apps/details?id={self._app_id}",
                raw_data={
                    "content": text,
                    "score": score,
                    "thumbsUpCount": review.get("thumbsUpCount", 0),
                    "reviewCreatedVersion": review.get("reviewCreatedVersion"),
                    "replyContent": review.get("replyContent"),
                },
            )
            mentions.append(mention)

        return mentions
