import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signalgraph.models.analysis import Theme
from signalgraph.pipeline.legitimacy import evaluate_legitimacy


def _make_theme(name: str, platforms: list[str] | None = None, mention_count: int = 5) -> Theme:
    now = datetime.now(timezone.utc)
    return Theme(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        name=name,
        summary=f"Summary for {name}",
        first_seen=now,
        last_seen=now,
        status="active",
        platforms=platforms or ["reddit"],
        mention_count=mention_count,
        avg_sentiment=-0.3,
    )


@pytest.mark.asyncio
async def test_evaluate_legitimacy_returns_scores():
    theme = _make_theme("Battery Drain Issues", platforms=["reddit", "appstore"], mention_count=42)

    mock_response_data = [
        {
            "theme_id": str(theme.id),
            "legitimacy_score": 0.85,
            "legitimacy_class": "organic",
            "reasoning": "Present on multiple platforms with gradual growth pattern.",
        }
    ]

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

    with patch("signalgraph.pipeline.legitimacy.anthropic") as mock_anthropic_module:
        mock_anthropic_module.AsyncAnthropic = mock_anthropic_class

        results = await evaluate_legitimacy([theme])

    assert len(results) == 1
    result = results[0]
    assert result["theme_id"] == str(theme.id)
    assert result["legitimacy_score"] == 0.85
    assert result["legitimacy_class"] == "organic"
    assert "multiple platforms" in result["reasoning"]


@pytest.mark.asyncio
async def test_evaluate_legitimacy_empty_list():
    results = await evaluate_legitimacy([])
    assert results == []


@pytest.mark.asyncio
async def test_evaluate_legitimacy_multiple_themes():
    theme_a = _make_theme("Camera Praise", platforms=["reddit"], mention_count=10)
    theme_b = _make_theme("Fake Reviews", platforms=["appstore"], mention_count=500)

    mock_response_data = [
        {
            "theme_id": str(theme_a.id),
            "legitimacy_score": 0.9,
            "legitimacy_class": "organic",
            "reasoning": "Normal distribution.",
        },
        {
            "theme_id": str(theme_b.id),
            "legitimacy_score": 0.2,
            "legitimacy_class": "suspected_coordinated",
            "reasoning": "Spike in mentions from new accounts.",
        },
    ]

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

    with patch("signalgraph.pipeline.legitimacy.anthropic") as mock_anthropic_module:
        mock_anthropic_module.AsyncAnthropic = mock_anthropic_class

        results = await evaluate_legitimacy([theme_a, theme_b])

    assert len(results) == 2
    ids = {r["theme_id"] for r in results}
    assert str(theme_a.id) in ids
    assert str(theme_b.id) in ids

    coordinated = next(r for r in results if r["theme_id"] == str(theme_b.id))
    assert coordinated["legitimacy_class"] == "suspected_coordinated"
    assert coordinated["legitimacy_score"] < 0.5
