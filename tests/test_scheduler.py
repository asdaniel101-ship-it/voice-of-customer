import pytest

from signalgraph.scheduler import get_scheduler, schedule_company


def test_get_scheduler_returns_instance():
    scheduler = get_scheduler()
    assert scheduler is not None
    # Returns the same instance on repeated calls
    assert get_scheduler() is scheduler


def test_schedule_company_adds_job():
    scheduler = get_scheduler()
    # Clear all existing jobs first
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    schedule_company(scheduler, company_id="abc-123", company_slug="acme", cron_expression="0 */6 * * *")
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "pipeline-acme"


def test_schedule_company_replaces_existing_job():
    scheduler = get_scheduler()
    # Clear all existing jobs first
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    # Add the same company twice
    schedule_company(scheduler, company_id="abc-123", company_slug="acme", cron_expression="0 */6 * * *")
    schedule_company(scheduler, company_id="abc-123", company_slug="acme", cron_expression="0 */12 * * *")

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "pipeline-acme"
