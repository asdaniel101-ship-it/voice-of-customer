import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.mention import RawMention
from signalgraph.schemas.mention import MentionResponse

router = APIRouter(prefix="/api/companies")


@router.get("/{company_id}/mentions", response_model=list[MentionResponse])
async def get_mentions(
    company_id: uuid.UUID,
    source: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[MentionResponse]:
    query = select(RawMention).where(RawMention.company_id == company_id)
    if source is not None:
        query = query.where(RawMention.source == source)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    mentions = result.scalars().all()
    return [MentionResponse.model_validate(m) for m in mentions]
