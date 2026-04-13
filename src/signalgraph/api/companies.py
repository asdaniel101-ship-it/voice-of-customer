import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from signalgraph.database import get_session
from signalgraph.models.company import Company
from signalgraph.pipeline.runner import run_pipeline
from signalgraph.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/api/companies")


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate, session: AsyncSession = Depends(get_session)
) -> CompanyResponse:
    company = Company(
        id=uuid.uuid4(),
        name=payload.name,
        slug=payload.slug,
        website=payload.website,
        search_terms=payload.search_terms,
        competitors=payload.competitors,
        sources=payload.sources,
        schedule=payload.schedule,
    )
    session.add(company)
    try:
        await session.commit()
        await session.refresh(company)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company with slug '{payload.slug}' already exists.",
        )
    return CompanyResponse.model_validate(company)


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    session: AsyncSession = Depends(get_session),
) -> list[CompanyResponse]:
    result = await session.execute(select(Company))
    companies = result.scalars().all()
    return [CompanyResponse.model_validate(c) for c in companies]


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> CompanyResponse:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return CompanyResponse.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    session: AsyncSession = Depends(get_session),
) -> CompanyResponse:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    await session.commit()
    await session.refresh(company)
    return CompanyResponse.model_validate(company)


@router.post("/{company_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline_run(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    sources = _build_sources(company.sources)
    run_id = await run_pipeline(company=company, sources=sources, session=session)
    return {"run_id": str(run_id), "status": "started"}


def _build_sources(source_config: dict) -> list:
    """Instantiate source adapters from company source config dict."""
    from signalgraph.sources.appstore import AppStoreSource
    from signalgraph.sources.hackernews import HackerNewsSource
    from signalgraph.sources.playstore import PlayStoreSource
    from signalgraph.sources.reddit import RedditSource
    from signalgraph.sources.trustpilot import TrustpilotSource

    sources = []
    for name, config in source_config.items():
        if name == "hackernews":
            sources.append(HackerNewsSource())
        elif name == "appstore" and config.get("app_id"):
            sources.append(AppStoreSource(app_id=config["app_id"]))
        elif name == "playstore" and config.get("app_id"):
            sources.append(PlayStoreSource(app_id=config["app_id"]))
        elif name == "trustpilot" and config.get("domain"):
            sources.append(TrustpilotSource(domain=config["domain"]))
        elif name == "reddit":
            sources.append(RedditSource())
    return sources


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    await session.delete(company)
    await session.commit()
