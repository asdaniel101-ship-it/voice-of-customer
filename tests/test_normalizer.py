from datetime import datetime, timezone

import pytest

from signalgraph.pipeline.normalizer import deduplicate, normalize_text
from signalgraph.sources.base import RawMentionData


def _make_mention(source: str, source_id: str, text: str = "hello") -> RawMentionData:
    return RawMentionData(
        source=source,
        source_id=source_id,
        text=text,
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_deduplicate_removes_same_source_id():
    mentions = [
        _make_mention("reddit", "abc123"),
        _make_mention("reddit", "abc123"),  # duplicate
        _make_mention("reddit", "def456"),
    ]
    result = deduplicate(mentions)
    assert len(result) == 2
    assert result[0].source_id == "abc123"
    assert result[1].source_id == "def456"


def test_normalize_text_cleans_whitespace():
    text = "  hello   world  \n  foo  "
    result = normalize_text(text)
    assert result == "hello world foo"


def test_normalize_text_strips_urls():
    text = "Check this out https://example.com/some/path and also http://foo.bar/baz"
    result = normalize_text(text)
    assert "https://" not in result
    assert "http://" not in result
    assert "Check this out" in result
    assert "and also" in result
