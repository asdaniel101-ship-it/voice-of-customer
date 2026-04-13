import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signalgraph.pipeline.analyzer import analyze_mentions
from signalgraph.models.mention import RawMention


def _make_raw_mention(mention_id: uuid.UUID, text: str, source: str = "reddit") -> RawMention:
    mention = RawMention(
        id=mention_id,
        company_id=uuid.uuid4(),
        source=source,
        source_id="test_source_id",
        text=text,
        published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        author="test_author",
    )
    return mention


@pytest.mark.asyncio
async def test_analyze_mentions_returns_results():
    mention_id_1 = uuid.uuid4()
    mention_id_2 = uuid.uuid4()
    run_id = uuid.uuid4()

    mentions = [
        _make_raw_mention(mention_id_1, "Battery life is terrible, drains in 2 hours"),
        _make_raw_mention(mention_id_2, "Love the new camera features, absolutely amazing"),
    ]

    mock_response_data = {
        "analysis_results": [
            {
                "mention_id": str(mention_id_1),
                "sentiment": -0.8,
                "sentiment_confidence": 0.9,
                "topics": ["battery life"],
            },
            {
                "mention_id": str(mention_id_2),
                "sentiment": 0.9,
                "sentiment_confidence": 0.95,
                "topics": ["camera", "features"],
            },
        ],
        "themes": [
            {
                "name": "Battery Issues",
                "summary": "Users reporting poor battery performance",
                "mention_ids": [str(mention_id_1)],
                "platforms": ["reddit"],
                "avg_sentiment": -0.8,
            },
            {
                "name": "Camera Praise",
                "summary": "Users praising the camera features",
                "mention_ids": [str(mention_id_2)],
                "platforms": ["reddit"],
                "avg_sentiment": 0.9,
            },
        ],
    }

    mock_response_text = "```json\n" + json.dumps(mock_response_data) + "\n```"

    mock_content_item = MagicMock()
    mock_content_item.text = mock_response_text

    mock_message = MagicMock()
    mock_message.content = [mock_content_item]

    mock_messages = AsyncMock()
    mock_messages.create = AsyncMock(return_value=mock_message)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    mock_anthropic_class = MagicMock(return_value=mock_client)

    with patch("signalgraph.pipeline.analyzer.anthropic") as mock_anthropic_module, \
         patch("signalgraph.config.settings") as mock_settings:
        mock_anthropic_module.AsyncAnthropic = mock_anthropic_class
        mock_settings.anthropic_api_key = "test-key"

        result = await analyze_mentions(
            mentions=mentions,
            company_name="TestCorp",
            run_id=run_id,
            history_summary="",
        )

    # Verify structure
    assert "analysis_results" in result
    assert "themes" in result

    analysis_results = result["analysis_results"]
    assert len(analysis_results) == 2

    # Check first result
    first = next(r for r in analysis_results if r["mention_id"] == str(mention_id_1))
    assert first["sentiment"] == -0.8
    assert first["sentiment_confidence"] == 0.9
    assert "battery life" in first["topics"]
    assert first["run_id"] == str(run_id)

    # Check second result
    second = next(r for r in analysis_results if r["mention_id"] == str(mention_id_2))
    assert second["sentiment"] == 0.9
    assert "camera" in second["topics"]
    assert second["run_id"] == str(run_id)

    # Check themes
    themes = result["themes"]
    assert len(themes) == 2

    battery_theme = next(t for t in themes if t["name"] == "Battery Issues")
    assert battery_theme["avg_sentiment"] == -0.8
    assert str(mention_id_1) in battery_theme["mention_ids"]
    assert battery_theme["run_id"] == str(run_id)
    assert "reddit" in battery_theme["platforms"]

    camera_theme = next(t for t in themes if t["name"] == "Camera Praise")
    assert camera_theme["avg_sentiment"] == 0.9


@pytest.mark.asyncio
async def test_analyze_mentions_empty_list():
    result = await analyze_mentions(
        mentions=[],
        company_name="TestCorp",
        run_id=uuid.uuid4(),
    )
    assert result == {"analysis_results": [], "themes": []}
