"""Celery task for scraping approved jobs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from loguru import logger

from app.db.models import Job, JobStatus, Run, RunStatus
from app.db.session import AsyncSessionLocal, engine
from app.services.job_events import publish_job_event
from app.services.scraper.dispatcher import get_scraper_dispatcher
from app.services.scraper.runner import scrape_job_sources
from app.worker import celery_app


@celery_app.task(name="jobs.run_scrape")
def run_scrape_task(job_id: str, run_id: str) -> dict[str, object]:
    """Run scraper worker for an approved job."""
    return asyncio.run(_run_scrape(job_id=job_id, run_id=run_id))


async def _run_scrape(*, job_id: str, run_id: str) -> dict[str, object]:
    job_uuid = UUID(job_id)
    run_uuid = UUID(run_id)
    await engine.dispose(close=False)
    try:
        return await _run_scrape_inner(
            job_id=job_id, run_id=run_id, job_uuid=job_uuid, run_uuid=run_uuid
        )
    finally:
        await engine.dispose()


async def _run_scrape_inner(
    *,
    job_id: str,
    run_id: str,
    job_uuid: UUID,
    run_uuid: UUID,
) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        try:
            job = await scrape_job_sources(
                session=session,
                job_id=job_uuid,
                run_id=run_uuid,
                dispatcher=get_scraper_dispatcher(),
            )
            await session.commit()
        except Exception as exc:
            await _safe_rollback(session)
            logger.opt(exception=exc).error(
                "Scrape task failed job_id={} run_id={}", job_id, run_id
            )
            await _mark_scrape_failed(job_uuid=job_uuid, run_uuid=run_uuid, message=str(exc))
            await publish_job_event(
                job_id=job_uuid,
                event_type="error",
                payload={"stage": "scrape", "message": str(exc)},
            )
            raise

    return {
        "status": job.status.value if job.status else JobStatus.FAILED.value,
        "job_id": job_id,
        "run_id": run_id,
        "records_added": job.total_records,
    }


async def _safe_rollback(session: object) -> None:
    try:
        await session.rollback()  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - best-effort failure cleanup
        logger.warning("Failed to rollback scrape task session: {}", exc)


async def _mark_scrape_failed(*, job_uuid: UUID, run_uuid: UUID, message: str) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_uuid)
        run = await session.get(Run, run_uuid)
        now = datetime.now(UTC)
        if job is not None:
            job.status = JobStatus.FAILED
            job.finished_at = now
        if run is not None:
            run.status = RunStatus.FAILED
            run.finished_at = now
            run.diff = {"error": message}
        await session.commit()
