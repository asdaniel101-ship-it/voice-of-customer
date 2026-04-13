import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.analysis import AnalysisResult, Theme
from signalgraph.models.mention import RawMention
from signalgraph.schemas.analysis import ThemeResponse
from signalgraph.schemas.mention import MentionResponse

router = APIRouter(prefix="/api")


@router.get("/companies/{company_id}/themes", response_model=list[ThemeResponse])
async def get_themes(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ThemeResponse]:
    result = await session.execute(
        select(Theme)
        .where(
            Theme.company_id == company_id,
            Theme.status.in_(["active", "emerging", "declining"]),
        )
        .order_by(Theme.mention_count.desc())
    )
    themes = result.scalars().all()
    return [ThemeResponse.model_validate(t) for t in themes]


@router.get("/themes/{theme_id}", response_model=ThemeResponse)
async def get_theme(
    theme_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ThemeResponse:
    theme = await session.get(Theme, theme_id)
    if theme is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")
    return ThemeResponse.model_validate(theme)


@router.get("/themes/{theme_id}/mentions")
async def get_theme_mentions(
    theme_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Get all mentions associated with a theme, with their analysis scores."""
    theme = await session.get(Theme, theme_id)
    if theme is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")

    # Get mention IDs from the theme's stored list
    theme_mention_ids = theme.mention_ids or []

    if not theme_mention_ids:
        return []

    # Fetch mentions and their analysis results
    mention_uuids = []
    for mid in theme_mention_ids:
        try:
            mention_uuids.append(uuid.UUID(mid))
        except (ValueError, AttributeError):
            continue

    if not mention_uuids:
        return []

    # Get mentions
    result = await session.execute(
        select(RawMention).where(RawMention.id.in_(mention_uuids))
    )
    mentions = {str(m.id): m for m in result.scalars().all()}

    # Get analysis results for these mentions
    result = await session.execute(
        select(AnalysisResult).where(AnalysisResult.mention_id.in_(mention_uuids))
    )
    analyses = {str(a.mention_id): a for a in result.scalars().all()}

    # Combine
    combined = []
    for mid_str in theme_mention_ids:
        mention = mentions.get(mid_str)
        analysis = analyses.get(mid_str)
        if mention:
            combined.append({
                "id": str(mention.id),
                "source": mention.source,
                "text": mention.text,
                "author": mention.author,
                "url": mention.url,
                "published_at": mention.published_at.isoformat() if mention.published_at else None,
                "sentiment": analysis.sentiment if analysis else None,
                "sentiment_confidence": analysis.sentiment_confidence if analysis else None,
                "topics": analysis.topics if analysis else [],
            })

    # Sort by sentiment (most negative first for actionability)
    combined.sort(key=lambda x: x.get("sentiment") or 0)

    return combined
