from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signalgraph.sources.appstore import AppStoreSource

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">
  <id>https://itunes.apple.com/us/rss/customerreviews/id=123456/sortBy=mostRecent/xml</id>
  <title>App Store Reviews</title>
  <entry>
    <id>1111111111</id>
    <title>Terrible battery drain</title>
    <content type="text">This app kills my battery in under an hour. Very disappointing.</content>
    <updated>2024-01-15T10:00:00Z</updated>
    <author>
      <name>angry_user</name>
    </author>
    <im:rating>1</im:rating>
    <im:version>2.1.0</im:version>
  </entry>
  <entry>
    <id>2222222222</id>
    <title>Amazing app, love it!</title>
    <content type="text">Best app I have ever used. Highly recommend to everyone.</content>
    <updated>2024-01-14T09:00:00Z</updated>
    <author>
      <name>happy_user</name>
    </author>
    <im:rating>5</im:rating>
    <im:version>2.1.0</im:version>
  </entry>
</feed>"""


@pytest.mark.asyncio
async def test_appstore_fetch_parses_rss():
    source = AppStoreSource(app_id="123456", country="us")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = MOCK_RSS_XML

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    since = datetime(2024, 1, 1, tzinfo=timezone.utc)

    with patch("signalgraph.sources.appstore.httpx.AsyncClient", return_value=mock_client):
        mentions = await source.fetch(["TestApp"], since)

    assert len(mentions) == 2

    # Check first mention (1-star)
    first = next(m for m in mentions if m.source_id == "1111111111")
    assert first.source == "appstore"
    assert "Terrible battery drain" in first.text
    assert "This app kills my battery in under an hour" in first.text
    assert first.author == "angry_user"
    assert first.author_metadata["rating"] == 1
    assert first.author_metadata["version"] == "2.1.0"
    assert first.published_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    # Check second mention (5-star)
    second = next(m for m in mentions if m.source_id == "2222222222")
    assert second.source == "appstore"
    assert "Amazing app, love it!" in second.text
    assert "Best app I have ever used" in second.text
    assert second.author == "happy_user"
    assert second.author_metadata["rating"] == 5
    assert second.author_metadata["version"] == "2.1.0"
    assert second.published_at == datetime(2024, 1, 14, 9, 0, 0, tzinfo=timezone.utc)


def test_appstore_source_name():
    source = AppStoreSource(app_id="123456", country="us")
    assert source.name == "appstore"
