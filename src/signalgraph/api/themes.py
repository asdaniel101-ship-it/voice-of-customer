import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.analysis import Theme
from signalgraph.schemas.analysis import ThemeResponse

router = APIRouter(prefix="/api/companies")


@router.get("/{company_id}/themes", response_model=list[ThemeResponse])
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
