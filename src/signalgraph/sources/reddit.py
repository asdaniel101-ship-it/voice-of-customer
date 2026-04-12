from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_SEARCH_URL = "https://oauth.reddit.com/search"
USER_AGENT = "signalgraph/0.1.0"


class RedditSource:
    name = "reddit"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    async def _get_token(self) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                REDDIT_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            return response.json()["access_token"]

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        token = await self._get_token()
        query = " OR ".join(search_terms)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                REDDIT_SEARCH_URL,
                params={"q": query, "sort": "new", "limit": 100, "type": "link"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": USER_AGENT,
                },
            )
            response.raise_for_status()
            data = response.json()

        mentions: list[RawMentionData] = []
        for post in data.get("data", {}).get("children", []):
            post_data = post.get("data", {})
            created_utc = post_data.get("created_utc", 0)
            published_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)

            if published_at < since:
                continue

            title = post_data.get("title", "")
            selftext = post_data.get("selftext", "")
            text = f"{title}\n{selftext}".strip() if selftext else title

            mention = RawMentionData(
                source="reddit",
                source_id=post_data.get("id", ""),
                text=text,
                published_at=published_at,
                author=post_data.get("author"),
                author_metadata={
                    "subreddit": post_data.get("subreddit"),
                    "score": post_data.get("score"),
                    "num_comments": post_data.get("num_comments"),
                },
                url=post_data.get("url"),
                raw_data=post_data,
            )
            mentions.append(mention)

        return mentions
