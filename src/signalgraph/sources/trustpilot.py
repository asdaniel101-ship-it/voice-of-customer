import json
import re
from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

TRUSTPILOT_URL = "https://www.trustpilot.com/review/{domain}"


class TrustpilotSource:
    """Fetch reviews from Trustpilot's public review pages.

    No API key needed. Uses the public web pages and extracts
    structured data from embedded JSON-LD and page markup.
    """

    name = "trustpilot"

    def __init__(self, domain: str) -> None:
        self._domain = domain

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        mentions: list[RawMentionData] = []

        # Fetch up to 10 pages of reviews (20 per page = 200 max)
        for page in range(1, 11):
            page_mentions = await self._fetch_page(page, since)
            mentions.extend(page_mentions)
            # Stop if we got fewer than expected (last page)
            if len(page_mentions) < 10:
                break

        return mentions

    async def _fetch_page(
        self, page: int, since: datetime
    ) -> list[RawMentionData]:
        url = f"https://www.trustpilot.com/review/{self._domain}?page={page}&sort=recency"

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            })
            if response.status_code != 200:
                return []
            html = response.text

        mentions: list[RawMentionData] = []

        # Method 1: Extract from JSON-LD structured data
        jsonld_mentions = self._parse_jsonld(html, since)
        if jsonld_mentions:
            return jsonld_mentions

        # Method 2: Extract from Next.js __NEXT_DATA__ JSON
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if next_data_match:
            try:
                next_data = json.loads(next_data_match.group(1))
                reviews = self._extract_from_next_data(next_data, since)
                if reviews:
                    return reviews
            except (json.JSONDecodeError, KeyError):
                pass

        # Method 3: Parse review cards from HTML
        review_cards = re.findall(
            r'<article[^>]*class="[^"]*paper_paper[^"]*"[^>]*>(.*?)</article>',
            html,
            re.DOTALL,
        )

        for i, card in enumerate(review_cards):
            text = self._extract_review_text(card)
            if not text:
                continue

            title = ""
            title_match = re.search(
                r'<h2[^>]*data-service-review-title-typography[^>]*>(.*?)</h2>',
                card, re.DOTALL,
            )
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

            full_text = f"{title}\n{text}".strip() if title else text

            author = None
            author_match = re.search(
                r'<span[^>]*data-consumer-name-typography[^>]*>(.*?)</span>',
                card, re.DOTALL,
            )
            if author_match:
                author = re.sub(r'<[^>]+>', '', author_match.group(1)).strip()

            rating = None
            rating_match = re.search(r'alt="Rated (\d) out of 5', card)
            if rating_match:
                rating = int(rating_match.group(1))

            date_str = None
            date_match = re.search(r'datetime="(\d{4}-\d{2}-\d{2})', card)
            published_at = datetime.now(tz=timezone.utc)
            if date_match:
                try:
                    published_at = datetime.fromisoformat(
                        date_match.group(1) + "T00:00:00+00:00"
                    )
                    if published_at < since:
                        continue
                except ValueError:
                    pass

            mention = RawMentionData(
                source="trustpilot",
                source_id=f"tp_{self._domain}_{page}_{i}",
                text=full_text,
                published_at=published_at,
                author=author,
                author_metadata={
                    "rating": rating,
                    "domain": self._domain,
                },
                url=f"https://www.trustpilot.com/review/{self._domain}",
                raw_data={"title": title, "text": text, "rating": rating},
            )
            mentions.append(mention)

        return mentions

    def _parse_jsonld(
        self, html: str, since: datetime
    ) -> list[RawMentionData]:
        """Extract reviews from JSON-LD structured data."""
        mentions: list[RawMentionData] = []

        jsonld_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
        )

        for block in jsonld_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict) and data.get("@type") == "LocalBusiness":
                    reviews = data.get("review", [])
                    for review in reviews:
                        if not isinstance(review, dict):
                            continue

                        text = review.get("reviewBody", "")
                        name = review.get("name", "")
                        full_text = f"{name}\n{text}".strip() if name else text

                        if not full_text:
                            continue

                        published_at = datetime.now(tz=timezone.utc)
                        date_str = review.get("datePublished", "")
                        if date_str:
                            try:
                                published_at = datetime.fromisoformat(
                                    date_str.replace("Z", "+00:00")
                                )
                            except ValueError:
                                pass

                        if published_at < since:
                            continue

                        author_data = review.get("author", {})
                        author = author_data.get("name") if isinstance(author_data, dict) else None

                        rating = None
                        rating_data = review.get("reviewRating", {})
                        if isinstance(rating_data, dict):
                            rating = rating_data.get("ratingValue")

                        mention = RawMentionData(
                            source="trustpilot",
                            source_id=f"tp_{self._domain}_{len(mentions)}",
                            text=full_text,
                            published_at=published_at,
                            author=author,
                            author_metadata={
                                "rating": rating,
                                "domain": self._domain,
                            },
                            url=f"https://www.trustpilot.com/review/{self._domain}",
                            raw_data={"name": name, "text": text, "rating": rating},
                        )
                        mentions.append(mention)
            except json.JSONDecodeError:
                continue

        return mentions

    def _extract_from_next_data(
        self, data: dict, since: datetime
    ) -> list[RawMentionData]:
        """Extract reviews from Next.js page data."""
        mentions: list[RawMentionData] = []

        try:
            # Navigate the Next.js data structure
            page_props = data.get("props", {}).get("pageProps", {})
            reviews = page_props.get("reviews", [])

            for review in reviews:
                text = review.get("text", "")
                title = review.get("title", "")
                full_text = f"{title}\n{text}".strip() if title else text

                if not full_text:
                    continue

                published_at = datetime.now(tz=timezone.utc)
                date_str = review.get("dates", {}).get("publishedDate", "")
                if date_str:
                    try:
                        published_at = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass

                if published_at < since:
                    continue

                consumer = review.get("consumer", {})
                author = consumer.get("displayName")

                rating = review.get("rating")
                review_id = review.get("id", f"tp_{self._domain}_{len(mentions)}")

                mention = RawMentionData(
                    source="trustpilot",
                    source_id=review_id,
                    text=full_text,
                    published_at=published_at,
                    author=author,
                    author_metadata={
                        "rating": rating,
                        "domain": self._domain,
                        "country": consumer.get("countryCode"),
                        "review_count": consumer.get("numberOfReviews"),
                    },
                    url=f"https://www.trustpilot.com/reviews/{review_id}",
                    raw_data=review,
                )
                mentions.append(mention)
        except (KeyError, TypeError):
            pass

        return mentions

    def _extract_review_text(self, card_html: str) -> str:
        """Extract review body text from a review card."""
        # Try data-service-review-text-typography first
        match = re.search(
            r'<p[^>]*data-service-review-text-typography[^>]*>(.*?)</p>',
            card_html, re.DOTALL,
        )
        if match:
            return re.sub(r'<[^>]+>', '', match.group(1)).strip()

        # Fallback to any paragraph with substantial text
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', card_html, re.DOTALL)
        for p in paragraphs:
            text = re.sub(r'<[^>]+>', '', p).strip()
            if len(text) > 20:
                return text

        return ""
