import uuid
from datetime import datetime, timezone

import pytest

from signalgraph.models.analysis import Theme
from signalgraph.pipeline.memory import build_history_summary, link_themes


def _make_theme(
    company_id: uuid.UUID,
    name: str,
    status: str = "active",
    mention_count: int = 5,
    avg_sentiment: float = 0.0,
    platforms: list[str] | None = None,
) -> Theme:
    now = datetime.now(timezone.utc)
    return Theme(
        id=uuid.uuid4(),
        company_id=company_id,
        run_id=uuid.uuid4(),
        name=name,
        summary=f"Summary for {name}",
        first_seen=now,
        last_seen=now,
        status=status,
        platforms=platforms or ["reddit"],
        mention_count=mention_count,
        avg_sentiment=avg_sentiment,
    )


@pytest.mark.asyncio
async def test_link_themes_matches_similar_names(db_session):
    from signalgraph.models.company import Company

    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        name="TestCorp",
        slug="testcorp-memory",
        search_terms=["testcorp"],
    )
    db_session.add(company)

    # Create an existing theme in the DB
    old_theme = _make_theme(
        company_id=company_id,
        name="Battery drain issues",
        status="active",
        mention_count=10,
        avg_sentiment=-0.5,
        platforms=["reddit"],
    )
    db_session.add(old_theme)
    await db_session.commit()

    # Create a new theme (not yet in DB — add it so delete works)
    new_theme = _make_theme(
        company_id=company_id,
        name="Battery drain after v4.2",
        status="emerging",
        mention_count=3,
        avg_sentiment=-0.6,
        platforms=["appstore"],
    )
    db_session.add(new_theme)
    await db_session.flush()

    linked = await link_themes(
        new_themes=[new_theme],
        company_id=company_id,
        session=db_session,
    )

    # Should have merged into old_theme
    assert len(linked) == 1
    merged = linked[0]
    assert merged.id == old_theme.id

    # mention_count should be summed
    assert merged.mention_count == 13

    # platforms should be merged
    assert set(merged.platforms) == {"reddit", "appstore"}


@pytest.mark.asyncio
async def test_build_history_summary(db_session):
    from signalgraph.models.company import Company

    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        name="HistoryCorp",
        slug="historycorp",
        search_terms=["historycorp"],
    )
    db_session.add(company)

    themes = [
        _make_theme(company_id, "Battery Issues", status="active"),
        _make_theme(company_id, "Camera Praise", status="emerging"),
        _make_theme(company_id, "Slow Performance", status="declining"),
    ]
    for t in themes:
        db_session.add(t)
    await db_session.commit()

    summary = await build_history_summary(company_id=company_id, session=db_session)

    assert "Battery Issues" in summary
    assert "Camera Praise" in summary
    assert "Slow Performance" in summary


@pytest.mark.asyncio
async def test_build_history_summary_empty(db_session):
    company_id = uuid.uuid4()
    summary = await build_history_summary(company_id=company_id, session=db_session)
    assert summary == "No prior themes detected."
