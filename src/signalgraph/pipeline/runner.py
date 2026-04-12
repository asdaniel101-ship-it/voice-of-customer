import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.models.analysis import AnalysisResult, Theme
from signalgraph.models.company import Company
from signalgraph.models.mention import RawMention
from signalgraph.pipeline.analyzer import analyze_mentions
from signalgraph.pipeline.legitimacy import evaluate_legitimacy
from signalgraph.pipeline.memory import build_history_summary, link_themes
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


async def save_analysis(
    analysis: dict,
    company_id: uuid.UUID,
    run_id: uuid.UUID,
    session: AsyncSession,
) -> list[Theme]:
    """Save analysis results and themes to the database. Returns list of Theme objects."""
    theme_objects: list[Theme] = []
    # Maps theme name to Theme object (used to look up theme_id by mention_id)
    mention_id_to_theme: dict[str, Theme] = {}

    now = datetime.now(timezone.utc)

    # Save themes first, flush to get IDs
    for theme_data in analysis.get("themes", []):
        theme = Theme(
            id=uuid.uuid4(),
            company_id=company_id,
            run_id=run_id,
            name=theme_data["name"],
            summary=theme_data["summary"],
            platforms=theme_data.get("platforms", []),
            avg_sentiment=theme_data.get("avg_sentiment", 0.0),
            mention_count=len(theme_data.get("mention_ids", [])),
            first_seen=now,
            last_seen=now,
        )
        session.add(theme)
        theme_objects.append(theme)

        for mid in theme_data.get("mention_ids", []):
            mention_id_to_theme[mid] = theme

    await session.flush()

    # Save AnalysisResult records
    for result_data in analysis.get("analysis_results", []):
        mention_id_str = result_data["mention_id"]
        theme = mention_id_to_theme.get(mention_id_str)

        analysis_result = AnalysisResult(
            id=uuid.uuid4(),
            company_id=company_id,
            run_id=run_id,
            mention_id=uuid.UUID(mention_id_str),
            sentiment=result_data["sentiment"],
            sentiment_confidence=result_data["sentiment_confidence"],
            topics=result_data.get("topics", []),
            theme_id=theme.id if theme else None,
        )
        session.add(analysis_result)

    await session.commit()
    return theme_objects


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

    mentions = await run_ingestion(company, sources, since, session)

    # Build history summary for context
    history_summary = await build_history_summary(company.id, session)

    analysis = await analyze_mentions(
        mentions=mentions,
        company_name=company.name,
        run_id=run_id,
        history_summary=history_summary,
    )

    themes = await save_analysis(analysis, company.id, run_id, session)

    # Link new themes to existing ones
    linked_themes = await link_themes(themes, company.id, session)

    # Evaluate legitimacy of linked themes
    legitimacy_results = await evaluate_legitimacy(linked_themes)

    # Update theme records with legitimacy data
    legitimacy_by_id = {r["theme_id"]: r for r in legitimacy_results}
    for theme in linked_themes:
        result = legitimacy_by_id.get(str(theme.id))
        if result:
            theme.legitimacy_score = result["legitimacy_score"]
            theme.legitimacy_class = result["legitimacy_class"]
            theme.legitimacy_reasoning = result["reasoning"]

    await session.commit()

    # TODO: generate brief (Task 13)

    return run_id
