import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.brief import Brief
from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention


def make_company(session: AsyncSession) -> Company:
    company = Company(
        id=uuid.uuid4(),
        name="TestCo",
        slug=f"testco-{uuid.uuid4().hex[:8]}",
        search_terms=["testco"],
    )
    session.add(company)
    return company


@pytest.mark.asyncio
async def test_get_mentions_for_company(client: AsyncClient, db_session: AsyncSession):
    company = make_company(db_session)
    await db_session.flush()

    mention = RawMention(
        id=uuid.uuid4(),
        company_id=company.id,
        source="reddit",
        source_id="abc123",
        author="user1",
        text="Great product!",
        url="https://reddit.com/r/test/abc123",
        published_at=datetime.now(timezone.utc),
        language="en",
        raw_data={},
    )
    db_session.add(mention)
    await db_session.commit()

    response = await client.get(f"/api/companies/{company.id}/mentions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["source"] == "reddit"
    assert data[0]["text"] == "Great product!"
    assert data[0]["author"] == "user1"


@pytest.mark.asyncio
async def test_get_latest_brief(client: AsyncClient, db_session: AsyncSession):
    company = make_company(db_session)
    await db_session.flush()

    run_id = uuid.uuid4()
    brief = Brief(
        id=uuid.uuid4(),
        company_id=company.id,
        run_id=run_id,
        content={"summary": "Top theme: Bug Reports", "emerging_themes": []},
        summary="Top theme: Bug Reports with 10 mentions.",
    )
    db_session.add(brief)
    await db_session.commit()

    response = await client.get(f"/api/companies/{company.id}/briefs")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Top theme: Bug Reports with 10 mentions."
    assert data["run_id"] == str(run_id)
    assert "content" in data
