import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention
from signalgraph.pipeline.normalizer import deduplicate, normalize_text
from signalgraph.sources.base import RawMentionData, Source


async def run_ingestion(
    company: Company,
    sources: list[Source],
    since: datetime,
    session: AsyncSession,
) -> list[RawMention]:
    """Fetch from all sources, deduplicate, normalize, and save RawMention records."""
    all_mentions: list[RawMentionData] = []
    for source in sources:
        fetched = await source.fetch(company.search_terms, since)
        all_mentions.extend(fetched)

    all_mentions = deduplicate(all_mentions)

    saved: list[RawMention] = []
    for mention_data in all_mentions:
        mention = RawMention(
            id=uuid.uuid4(),
            company_id=company.id,
            source=mention_data.source,
            source_id=mention_data.source_id,
            text=normalize_text(mention_data.text),
            published_at=mention_data.published_at,
            author=mention_data.author,
            author_metadata=mention_data.author_metadata,
            url=mention_data.url,
            language=mention_data.language,
            raw_data=mention_data.raw_data,
        )
        session.add(mention)
        saved.append(mention)

    await session.commit()
    return saved


async def run_pipeline(
    company: Company,
    sources: list[Source],
    session: AsyncSession,
    since: datetime | None = None,
) -> uuid.UUID:
    """Run the full ingestion pipeline for a company. Returns a run_id UUID."""
    run_id = uuid.uuid4()

    if since is None:
        since = datetime.now(tz=timezone.utc) - timedelta(days=1)

    await run_ingestion(company, sources, since, session)

    # TODO: run analysis step (Task 8)
    # TODO: run legitimacy filter (Task 12)
    # TODO: generate brief (Task 13)

    return run_id
