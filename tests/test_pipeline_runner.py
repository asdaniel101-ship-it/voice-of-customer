import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from signalgraph.models.analysis import AnalysisResult, Theme
from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention
from signalgraph.pipeline.runner import run_pipeline
from signalgraph.sources.base import RawMentionData


class FakeSource:
    name = "reddit"

    async def fetch(self, search_terms: list[str], since: datetime) -> list[RawMentionData]:
        return [
            RawMentionData(
                source="reddit",
                source_id="fake_post_1",
                text="Battery drains way too fast on this phone",
                published_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                author="user_a",
            ),
            RawMentionData(
                source="reddit",
                source_id="fake_post_2",
                text="The camera is absolutely incredible, best I have ever used",
                published_at=datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
                author="user_b",
            ),
        ]


@pytest.mark.asyncio
async def test_run_pipeline_saves_mentions_and_analysis(db_session):
    # Create a company
    company = Company(
        id=uuid.uuid4(),
        name="TestCorp",
        slug="testcorp",
        search_terms=["testcorp"],
    )
    db_session.add(company)
    await db_session.commit()

    # Build mock analyze_mentions that uses actual mention IDs
    async def fake_analyze_mentions(mentions, company_name, run_id, history_summary=""):
        analysis_results = []
        themes_data = []

        for i, mention in enumerate(mentions):
            mid = str(mention.id)
            sentiment = -0.7 if i == 0 else 0.8
            analysis_results.append({
                "mention_id": mid,
                "sentiment": sentiment,
                "sentiment_confidence": 0.9,
                "topics": ["battery"] if i == 0 else ["camera"],
                "run_id": str(run_id),
            })

        # Create two themes
        if len(mentions) >= 2:
            themes_data = [
                {
                    "name": "Battery Issues",
                    "summary": "Users complaining about battery",
                    "mention_ids": [str(mentions[0].id)],
                    "platforms": ["reddit"],
                    "avg_sentiment": -0.7,
                    "run_id": str(run_id),
                },
                {
                    "name": "Camera Praise",
                    "summary": "Users loving the camera",
                    "mention_ids": [str(mentions[1].id)],
                    "platforms": ["reddit"],
                    "avg_sentiment": 0.8,
                    "run_id": str(run_id),
                },
            ]

        return {"analysis_results": analysis_results, "themes": themes_data}

    async def fake_link_themes(themes, company_id, session, similarity_threshold=0.3):
        return themes

    async def fake_evaluate_legitimacy(themes):
        return []

    with (
        patch("signalgraph.pipeline.runner.analyze_mentions", side_effect=fake_analyze_mentions),
        patch("signalgraph.pipeline.runner.build_history_summary", return_value="No prior themes detected."),
        patch("signalgraph.pipeline.runner.link_themes", side_effect=fake_link_themes),
        patch("signalgraph.pipeline.runner.evaluate_legitimacy", side_effect=fake_evaluate_legitimacy),
    ):
        run_id = await run_pipeline(
            company=company,
            sources=[FakeSource()],
            session=db_session,
        )

    assert isinstance(run_id, uuid.UUID)

    # Verify RawMention records
    result = await db_session.execute(
        select(RawMention).where(RawMention.company_id == company.id)
    )
    raw_mentions = result.scalars().all()
    assert len(raw_mentions) == 2
    sources = {m.source_id for m in raw_mentions}
    assert "fake_post_1" in sources
    assert "fake_post_2" in sources

    # Verify AnalysisResult records
    result = await db_session.execute(
        select(AnalysisResult).where(AnalysisResult.run_id == run_id)
    )
    analysis_results = result.scalars().all()
    assert len(analysis_results) == 2

    sentiments = {r.sentiment for r in analysis_results}
    assert -0.7 in sentiments
    assert 0.8 in sentiments

    # Verify Theme records
    result = await db_session.execute(
        select(Theme).where(Theme.run_id == run_id)
    )
    themes = result.scalars().all()
    assert len(themes) == 2

    theme_names = {t.name for t in themes}
    assert "Battery Issues" in theme_names
    assert "Camera Praise" in theme_names

    # Verify theme_id is set on analysis results
    for ar in analysis_results:
        assert ar.theme_id is not None


@pytest.mark.asyncio
async def test_full_pipeline_with_memory_and_legitimacy(db_session):
    """Test that the full pipeline calls memory and legitimacy stages."""
    company = Company(
        id=uuid.uuid4(),
        name="FullPipelineCorp",
        slug="fullpipelinecorp",
        search_terms=["fullpipelinecorp"],
    )
    db_session.add(company)
    await db_session.commit()

    captured_theme_id = None

    async def fake_analyze_mentions(mentions, company_name, run_id, history_summary=""):
        results = []
        themes_data = []
        for i, mention in enumerate(mentions):
            mid = str(mention.id)
            sentiment = -0.5 if i == 0 else 0.5
            results.append({
                "mention_id": mid,
                "sentiment": sentiment,
                "sentiment_confidence": 0.9,
                "topics": ["topic"],
                "run_id": str(run_id),
            })
        if mentions:
            themes_data.append({
                "name": "Test Theme",
                "summary": "A test theme",
                "mention_ids": [str(mentions[0].id)],
                "platforms": ["reddit"],
                "avg_sentiment": -0.5,
                "run_id": str(run_id),
            })
        return {"analysis_results": results, "themes": themes_data}

    async def fake_link_themes(themes, company_id, session, similarity_threshold=0.3):
        nonlocal captured_theme_id
        if themes:
            captured_theme_id = themes[0].id
        return themes

    async def fake_evaluate_legitimacy(themes):
        if not themes:
            return []
        return [
            {
                "theme_id": str(themes[0].id),
                "legitimacy_score": 0.75,
                "legitimacy_class": "organic",
                "reasoning": "Looks legitimate.",
            }
        ]

    mock_build_history = AsyncMock(return_value="No prior themes detected.")

    with (
        patch("signalgraph.pipeline.runner.analyze_mentions", side_effect=fake_analyze_mentions),
        patch("signalgraph.pipeline.runner.build_history_summary", mock_build_history),
        patch("signalgraph.pipeline.runner.link_themes", side_effect=fake_link_themes),
        patch("signalgraph.pipeline.runner.evaluate_legitimacy", side_effect=fake_evaluate_legitimacy),
    ):
        run_id = await run_pipeline(
            company=company,
            sources=[FakeSource()],
            session=db_session,
        )

    assert isinstance(run_id, uuid.UUID)

    # Verify build_history_summary was called
    mock_build_history.assert_called_once()

    # Verify theme has legitimacy data
    assert captured_theme_id is not None
    result = await db_session.execute(
        select(Theme).where(Theme.id == captured_theme_id)
    )
    theme = result.scalar_one()
    assert theme.legitimacy_score == 0.75
    assert theme.legitimacy_class == "organic"
    assert theme.legitimacy_reasoning == "Looks legitimate."
