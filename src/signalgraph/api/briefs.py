import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.brief import Brief
from signalgraph.schemas.brief import BriefResponse

router = APIRouter(prefix="/api/companies")


@router.get("/{company_id}/briefs", response_model=BriefResponse)
async def get_latest_brief(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> BriefResponse:
    result = await session.execute(
        select(Brief)
        .where(Brief.company_id == company_id)
        .order_by(Brief.created_at.desc())
        .limit(1)
    )
    brief = result.scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No briefs found for this company.")
    return BriefResponse.model_validate(brief)
