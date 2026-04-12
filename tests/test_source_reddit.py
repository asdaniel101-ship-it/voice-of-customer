from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signalgraph.sources.reddit import RedditSource


def _make_post(post_id: str, title: str, selftext: str = "", created_utc: float = 1_700_000_000.0) -> dict:
    return {
        "data": {
            "id": post_id,
            "title": title,
            "selftext": selftext,
            "author": "test_user",
            "subreddit": "testsubreddit",
            "score": 42,
            "num_comments": 7,
            "url": f"https://reddit.com/r/testsubreddit/comments/{post_id}",
            "created_utc": created_utc,
        }
    }


MOCK_TOKEN_RESPONSE = {"access_token": "mock-token", "token_type": "bearer"}

MOCK_SEARCH_RESPONSE = {
    "data": {
        "children": [
            _make_post("abc123", "Post about acme", "Some body text", 1_700_000_100.0),
            _make_post("def456", "Another acme mention", created_utc=1_700_000_200.0),
        ]
    }
}


@pytest.mark.asyncio
async def test_reddit_fetch_returns_mentions():
    source = RedditSource(client_id="id", client_secret="secret")

    token_resp = MagicMock()
    token_resp.raise_for_status = MagicMock()
    token_resp.json = MagicMock(return_value=MOCK_TOKEN_RESPONSE)

    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json = MagicMock(return_value=MOCK_SEARCH_RESPONSE)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=token_resp)
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("signalgraph.sources.reddit.httpx.AsyncClient", return_value=mock_client):
        since = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mentions = await source.fetch(["acme"], since)

    assert len(mentions) == 2

    first = mentions[0]
    assert first.source == "reddit"
    assert first.source_id == "abc123"
    assert "Post about acme" in first.text
    assert "Some body text" in first.text
    assert first.author == "test_user"
    assert first.author_metadata["subreddit"] == "testsubreddit"
    assert first.author_metadata["score"] == 42
    assert first.author_metadata["num_comments"] == 7

    second = mentions[1]
    assert second.source_id == "def456"
    assert second.text == "Another acme mention"


@pytest.mark.asyncio
async def test_reddit_source_has_correct_name():
    source = RedditSource(client_id="id", client_secret="secret")
    assert source.name == "reddit"
