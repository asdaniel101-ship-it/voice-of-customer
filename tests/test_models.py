from datetime import datetime, timezone

from sqlalchemy import select

from signalgraph.models import Company, RawMention


async def test_create_company(db_session):
    company = Company(
        name="Acme Corp",
        slug="acme-corp",
        search_terms=["Acme", "AcmePro"],
    )
    db_session.add(company)
    await db_session.commit()

    result = await db_session.execute(select(Company).where(Company.slug == "acme-corp"))
    saved = result.scalar_one()
    assert saved.name == "Acme Corp"
    assert saved.search_terms == ["Acme", "AcmePro"]
    assert saved.active is True


async def test_create_mention(db_session):
    company = Company(name="Test Co", slug="test-co", search_terms=["test"])
    db_session.add(company)
    await db_session.commit()

    mention = RawMention(
        company_id=company.id,
        source="reddit",
        source_id="abc123",
        text="This product is great",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(mention)
    await db_session.commit()

    result = await db_session.execute(
        select(RawMention).where(RawMention.company_id == company.id)
    )
    saved = result.scalar_one()
    assert saved.text == "This product is great"
    assert saved.source == "reddit"
