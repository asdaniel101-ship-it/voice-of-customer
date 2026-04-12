from datetime import datetime, timezone

import httpx

from signalgraph.sources.base import RawMentionData

YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YT_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


class YouTubeSource:
    name = "youtube"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch(
        self, search_terms: list[str], since: datetime
    ) -> list[RawMentionData]:
        query = " ".join(search_terms)
        published_after = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        mentions: list[RawMentionData] = []

        async with httpx.AsyncClient() as client:
            # Step 1: Search for videos
            search_resp = await client.get(
                YT_SEARCH_URL,
                params={
                    "key": self._api_key,
                    "q": query,
                    "part": "snippet",
                    "type": "video",
                    "publishedAfter": published_after,
                    "maxResults": 50,
                    "order": "date",
                },
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()

            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if item.get("id", {}).get("videoId")
            ]

            if not video_ids:
                return mentions

            # Step 2: Fetch comments for videos
            comments_resp = await client.get(
                YT_COMMENTS_URL,
                params={
                    "key": self._api_key,
                    "videoId": ",".join(video_ids[:10]),  # limit to avoid quota issues
                    "part": "snippet",
                    "maxResults": 100,
                    "order": "time",
                },
            )
            comments_resp.raise_for_status()
            comments_data = comments_resp.json()

        for item in comments_data.get("items", []):
            top_level = item.get("snippet", {}).get("topLevelComment", {})
            snippet = top_level.get("snippet", {})

            published_at_str = snippet.get("publishedAt", "")
            try:
                published_at = datetime.fromisoformat(
                    published_at_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                published_at = datetime.now(tz=timezone.utc)

            comment_id = top_level.get("id", item.get("id", ""))
            video_id = snippet.get("videoId", "")
            text = snippet.get("textOriginal") or snippet.get("textDisplay", "")

            mention = RawMentionData(
                source="youtube",
                source_id=comment_id,
                text=text,
                published_at=published_at,
                author=snippet.get("authorDisplayName"),
                author_metadata={
                    "like_count": snippet.get("likeCount"),
                    "video_id": video_id,
                    "reply_count": item.get("snippet", {}).get("totalReplyCount"),
                },
                url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                raw_data=item,
            )
            mentions.append(mention)

        return mentions
