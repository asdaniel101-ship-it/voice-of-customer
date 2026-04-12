import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def parse_cron(expression: str) -> dict:
    parts = expression.split()
    if len(parts) != 5:
        return {"hour": "*/6"}
    return {"minute": parts[0], "hour": parts[1], "day": parts[2], "month": parts[3], "day_of_week": parts[4]}


def schedule_company(scheduler, company_id, company_slug, cron_expression):
    job_id = f"pipeline-{company_slug}"
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)
    cron_kwargs = parse_cron(cron_expression)
    trigger = CronTrigger(**cron_kwargs)
    scheduler.add_job(_run_company_pipeline, trigger=trigger, id=job_id, kwargs={"company_id": company_id}, replace_existing=True)


async def _run_company_pipeline(company_id: str) -> None:
    from signalgraph.database import SessionLocal
    from signalgraph.models.company import Company
    from signalgraph.pipeline.runner import run_pipeline
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company or not company.active:
            return
        try:
            run_id = await run_pipeline(company=company, sources=[], session=session)
            logger.info(f"Pipeline completed for {company.slug}: run_id={run_id}")
        except Exception:
            logger.exception(f"Pipeline failed for {company.slug}")
