import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.analysis import Theme
from signalgraph.models.company import Company
from signalgraph.pipeline.briefer import generate_brief


def make_company(session: AsyncSession) -> Company:
    company = Company(
        id=uuid.uuid4(),
        name="TestCo",
        slug="testco",
        search_terms=["testco"],
    )
    session.add(company)
    return company


@pytest.mark.asyncio
async def test_generate_brief_from_themes(db_session: AsyncSession):
    company = make_company(db_session)
    await db_session.flush()

    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    theme_active = Theme(
        id=uuid.uuid4(),
        company_id=company.id,
        run_id=run_id,
        name="Performance Issues",
        summary="Users reporting slowness",
        status="active",
        platforms=["reddit", "appstore"],
        mention_count=42,
        avg_sentiment=-0.5,
        legitimacy_score=0.9,
        legitimacy_class="suspected_coordinated",
        first_seen=now,
        last_seen=now,
    )
    theme_emerging = Theme(
        id=uuid.uuid4(),
        company_id=company.id,
        run_id=run_id,
        name="New Feature Request",
        summary="Users want dark mode",
        status="emerging",
        platforms=["reddit"],
        mention_count=15,
        avg_sentiment=0.3,
        legitimacy_score=0.2,
        legitimacy_class="organic",
        first_seen=now,
        last_seen=now,
    )
    db_session.add(theme_active)
    db_session.add(theme_emerging)
    await db_session.commit()

    brief = await generate_brief(company, run_id, db_session)

    assert "Performance Issues" in brief["summary"]
    assert "42" in brief["summary"]

    assert len(brief["emerging_themes"]) == 1
    assert brief["emerging_themes"][0]["name"] == "New Feature Request"

    assert len(brief["trending_themes"]) == 1
    assert brief["trending_themes"][0]["name"] == "Performance Issues"

    assert len(brief["legitimacy_alerts"]) == 1
    assert brief["legitimacy_alerts"][0]["legitimacy_class"] == "suspected_coordinated"

    assert len(brief["competitive_signals"]) == 0

    # theme_active has 42 mentions, negative sentiment, legitimacy_score 0.9 > 0.7
    assert len(brief["recommended_actions"]) == 1
    assert "Performance Issues" in brief["recommended_actions"][0]


@pytest.mark.asyncio
async def test_generate_brief_empty_themes(db_session: AsyncSession):
    company = make_company(db_session)
    await db_session.flush()
    await db_session.commit()

    run_id = uuid.uuid4()
    brief = await generate_brief(company, run_id, db_session)

    assert brief["summary"] == "No significant themes detected in this run."
    assert brief["emerging_themes"] == []
    assert brief["trending_themes"] == []
    assert brief["legitimacy_alerts"] == []
    assert brief["competitive_signals"] == []
    assert brief["recommended_actions"] == []
