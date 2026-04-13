from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signalgraph.sources.hackernews import HackerNewsSource
from signalgraph.sources.youtube import YouTubeSource


MOCK_HN_RESPONSE = {
    "hits": [
        {
            "objectID": "hn001",
            "title": "Ask HN: Anyone using Acme Corp?",
            "story_text": "Looking for feedback on Acme Corp's product.",
            "author": "hn_user_1",
            "created_at_i": 1_700_000_100,
            "points": 15,
            "num_comments": 3,
            "story_id": None,
            "_tags": ["story"],
            "url": "https://news.ycombinator.com/item?id=hn001",
        },
        {
            "objectID": "hn002",
            "title": "",
            "comment_text": "Acme Corp has great customer support in my experience.",
            "author": "hn_user_2",
            "created_at_i": 1_700_000_200,
            "points": None,
            "num_comments": None,
            "story_id": "hn001",
            "_tags": ["comment"],
            "url": None,
        },
    ]
}


@pytest.mark.asyncio
async def test_hackernews_fetch():
    source = HackerNewsSource()

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.raise_for_status = MagicMock()
    search_resp.json = MagicMock(return_value={**MOCK_HN_RESPONSE, "nbPages": 1})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("signalgraph.sources.hackernews.httpx.AsyncClient", return_value=mock_client):
        since = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mentions = await source.fetch(["acme"], since)

    assert len(mentions) == 2

    story = mentions[0]
    assert story.source == "hackernews"
    assert story.source_id == "hn001"
    assert "Ask HN: Anyone using Acme Corp?" in story.text
    assert "Looking for feedback" in story.text
    assert story.author == "hn_user_1"
    assert story.author_metadata["points"] == 15

    comment = mentions[1]
    assert comment.source_id == "hn002"
    assert "great customer support" in comment.text
    assert comment.author == "hn_user_2"
    assert comment.author_metadata["story_id"] == "hn001"


MOCK_YT_SEARCH_RESPONSE = {
    "items": [
        {
            "id": {"videoId": "vid001"},
            "snippet": {
                "title": "Acme Corp Review 2023",
                "publishedAt": "2023-11-14T12:00:00Z",
            },
        }
    ]
}

MOCK_YT_COMMENTS_RESPONSE = {
    "items": [
        {
            "id": "comment_thread_001",
            "snippet": {
                "totalReplyCount": 2,
                "topLevelComment": {
                    "id": "comment001",
                    "snippet": {
                        "videoId": "vid001",
                        "textOriginal": "Love Acme Corp's new features!",
                        "authorDisplayName": "yt_user_1",
                        "likeCount": 5,
                        "publishedAt": "2023-11-14T13:00:00Z",
                    },
                },
            },
        },
        {
            "id": "comment_thread_002",
            "snippet": {
                "totalReplyCount": 0,
                "topLevelComment": {
                    "id": "comment002",
                    "snippet": {
                        "videoId": "vid001",
                        "textOriginal": "Acme Corp needs to fix their UI.",
                        "authorDisplayName": "yt_user_2",
                        "likeCount": 1,
                        "publishedAt": "2023-11-14T14:00:00Z",
                    },
                },
            },
        },
    ]
}


@pytest.mark.asyncio
async def test_youtube_fetch():
    source = YouTubeSource(api_key="fake-api-key")

    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json = MagicMock(return_value=MOCK_YT_SEARCH_RESPONSE)

    comments_resp = MagicMock()
    comments_resp.raise_for_status = MagicMock()
    comments_resp.json = MagicMock(return_value=MOCK_YT_COMMENTS_RESPONSE)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[search_resp, comments_resp])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("signalgraph.sources.youtube.httpx.AsyncClient", return_value=mock_client):
        since = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mentions = await source.fetch(["acme"], since)

    assert len(mentions) == 2

    first = mentions[0]
    assert first.source == "youtube"
    assert first.source_id == "comment001"
    assert "Love Acme Corp's new features!" in first.text
    assert first.author == "yt_user_1"
    assert first.author_metadata["like_count"] == 5
    assert first.author_metadata["video_id"] == "vid001"

    second = mentions[1]
    assert second.source_id == "comment002"
    assert "fix their UI" in second.text
    assert second.author == "yt_user_2"
