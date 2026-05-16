"""Celery task for asynchronous source discovery."""

from __future__ import annotations

import asyncio
from uuid import UUID

from loguru import logger

from app.db.models import Job, JobStatus
from app.db.session import AsyncSessionLocal, engine
from app.services.job_events import publish_job_event
from app.services.source_discovery import get_source_discovery
from app.services.source_persistence import discover_and_persist_sources
from app.worker import celery_app


@celery_app.task(name="jobs.discover_sources")
def discover_sources_task(job_id: str) -> dict[str, object]:
    """Run source discovery in the worker process."""
    return asyncio.run(_discover_sources(job_id))


async def _discover_sources(job_id: str) -> dict[str, object]:
    job_uuid = UUID(job_id)
    await engine.dispose(close=False)
    try:
        return await _discover_sources_inner(job_id=job_id, job_uuid=job_uuid)
    finally:
        await engine.dispose()


async def _discover_sources_inner(*, job_id: str, job_uuid: UUID) -> dict[str, object]:
    await publish_job_event(
        job_id=job_uuid,
        event_type="progress",
        payload={"stage": "source_discovery", "status": "started", "progress": 0.1},
    )
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_uuid)
        if job is None:
            await publish_job_event(
                job_id=job_uuid,
                event_type="error",
                payload={"stage": "source_discovery", "message": "job not found"},
            )
            return {"status": "not_found", "job_id": job_id}

        if job.status != JobStatus.PLANNING:
            await publish_job_event(
                job_id=job_uuid,
                event_type="error",
                payload={
                    "stage": "source_discovery",
                    "message": f"job status must be planning, got {job.status.value}",
                },
            )
            return {"status": "invalid_status", "job_id": job_id}

        try:
            await publish_job_event(
                job_id=job_uuid,
                event_type="progress",
                payload={"stage": "source_discovery", "status": "discovering", "progress": 0.35},
            )
            plan = await discover_and_persist_sources(
                session=session,
                job=job,
                discovery=get_source_discovery(),
            )
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.opt(exception=exc).error("Source discovery task failed job_id={}", job_id)
            await publish_job_event(
                job_id=job_uuid,
                event_type="error",
                payload={"stage": "source_discovery", "message": str(exc)},
            )
            raise

    await publish_job_event(
        job_id=job_uuid,
        event_type="done",
        payload={
            "stage": "source_discovery",
            "status": "done",
            "progress": 1,
            "source_count": len(plan.sources),
        },
    )
    return {"status": "done", "job_id": job_id, "source_count": len(plan.sources)}
