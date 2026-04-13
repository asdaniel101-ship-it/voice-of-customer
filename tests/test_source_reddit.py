from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signalgraph.sources.reddit import RedditSource

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>t3_abc123</id>
    <title>Post about acme products</title>
    <content type="html">&lt;p&gt;Some body text about acme&lt;/p&gt;</content>
    <updated>2023-11-15T12:00:00+00:00</updated>
    <author><name>/u/test_user</name></author>
    <link href="https://www.reddit.com/r/testsubreddit/comments/abc123/post_about_acme/"/>
    <category term="testsubreddit"/>
  </entry>
  <entry>
    <id>t3_def456</id>
    <title>Another acme mention in the wild</title>
    <content type="html">&lt;p&gt;More text here&lt;/p&gt;</content>
    <updated>2023-11-15T13:00:00+00:00</updated>
    <author><name>/u/other_user</name></author>
    <link href="https://www.reddit.com/r/technology/comments/def456/another_acme/"/>
    <category term="technology"/>
  </entry>
</feed>"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""


@pytest.mark.asyncio
async def test_reddit_fetch_returns_mentions():
    source = RedditSource(subreddits=[])  # No subreddits to keep test simple

    mock_response_with_data = MagicMock()
    mock_response_with_data.status_code = 200
    mock_response_with_data.text = SAMPLE_RSS

    mock_response_empty = MagicMock()
    mock_response_empty.status_code = 200
    mock_response_empty.text = EMPTY_RSS

    mock_client = AsyncMock()
    # First call (r/all search) returns data, subsequent calls return empty
    mock_client.get = AsyncMock(side_effect=[mock_response_with_data, mock_response_empty])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("signalgraph.sources.reddit.httpx.AsyncClient", return_value=mock_client):
        since = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mentions = await source.fetch(["acme"], since)

    assert len(mentions) >= 2

    first = mentions[0]
    assert first.source == "reddit"
    assert "t3_abc123" in first.source_id
    assert "Post about acme" in first.text
    assert first.author == "test_user"
    assert first.author_metadata["subreddit"] == "testsubreddit"


@pytest.mark.asyncio
async def test_reddit_source_has_correct_name():
    source = RedditSource()
    assert source.name == "reddit"
