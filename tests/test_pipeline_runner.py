import uuid
from datetime import datetime, timezone
from unittest.mock import patch

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

    with patch("signalgraph.pipeline.runner.analyze_mentions", side_effect=fake_analyze_mentions):
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
