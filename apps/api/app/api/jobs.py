"""Jobs CRUD endpoints (Phase 1).

POST /jobs        — create job dari prompt (otomatis parse intent → simpan plan).
GET  /jobs        — list jobs untuk user (Phase 1 single-user, no filter).
GET  /jobs/{id}   — detail job + parsed plan.
PATCH /jobs/{id}/intent  — user edit fields/filters di plan.
POST  /jobs/{id}/reparse — edit prompt and parse plan again.
POST  /jobs/{id}/discover — discover source candidates + persist pending sources.
PATCH /jobs/{id}/sources  — user enable/skip source candidates.
POST  /jobs/{id}/run      — approve plan and hand off to scraper worker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, JobStatus, Run, RunStatus, RunTrigger, Source, SourceStatus
from app.db.session import get_session
from app.schemas.intent import Plan
from app.schemas.jobs import (
    JobCreate,
    JobIntentUpdate,
    JobListItem,
    JobListResponse,
    JobRead,
    JobReparse,
    JobSourcesUpdate,
)
from app.services.intent_parser import IntentParserProtocol, get_intent_parser
from app.services.job_events import publish_job_event
from app.services.scraper.dispatcher import get_scraper_dispatcher
from app.services.scraper.runner import scrape_job_sources
from app.services.source_discovery import SourceDiscoveryProtocol, get_source_discovery
from app.services.source_persistence import discover_and_persist_sources, source_row_to_plan
from app.tasks.scrape import run_scrape_task
from app.tasks.source_discovery import discover_sources_task

router = APIRouter(prefix="/jobs", tags=["jobs"])

ParserDep = Annotated[IntentParserProtocol, Depends(get_intent_parser)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
DiscoveryDep = Annotated[SourceDiscoveryProtocol, Depends(get_source_discovery)]


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create job + parse intent",
)
async def create_job(
    payload: JobCreate,
    session: SessionDep,
    parser: ParserDep,
) -> Job:
    """Terima prompt user, parse intent, persist sebagai job draft."""
    plan = await parser.parse(payload.prompt)
    job = Job(
        prompt=payload.prompt.strip(),
        parsed_plan=plan.model_dump(mode="json"),
        status=JobStatus.PLANNING,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    logger.info(
        "Job created id={} entity={} fields={}",
        job.id,
        plan.intent.entity_type,
        len(plan.intent.required_fields),
    )
    return job


@router.get("", response_model=JobListResponse, summary="List jobs (newest first)")
async def list_jobs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
) -> JobListResponse:
    """Pagination simple. Phase 2 akan filter by user_id."""
    base_stmt = select(Job)
    count_stmt = select(func.count()).select_from(Job)
    if job_status is not None:
        base_stmt = base_stmt.where(Job.status == job_status)
        count_stmt = count_stmt.where(Job.status == job_status)

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = base_stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    items = [JobListItem.model_validate(row) for row in rows]
    return JobListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobRead, summary="Get job by id")
async def get_job(job_id: UUID, session: SessionDep) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


@router.patch(
    "/{job_id}/intent",
    response_model=JobRead,
    summary="Update parsed intent (user-edited plan)",
)
async def update_job_intent(
    job_id: UUID,
    payload: JobIntentUpdate,
    session: SessionDep,
) -> Job:
    """Replace `parsed_plan.intent` dengan versi yang sudah di-edit user.

    Sources di plan dipertahankan (Phase 1.3 source discovery yang isi).
    Hanya boleh kalau status masih `planning` (belum dispatch ke worker).
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.status != JobStatus.PLANNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot edit intent for job in status '{job.status.value}'; "
                "intent edit hanya boleh di 'planning'."
            ),
        )

    # Preserve sources + warnings; replace intent dgn versi user.
    existing = (
        Plan.model_validate(job.parsed_plan)
        if job.parsed_plan
        else Plan(
            intent=payload.intent,
        )
    )
    new_plan = Plan(
        intent=payload.intent,
        sources=existing.sources,
        estimated_record_count=existing.estimated_record_count,
        warnings=existing.warnings,
    )
    job.parsed_plan = new_plan.model_dump(mode="json")
    await session.commit()
    await session.refresh(job)

    logger.info(
        "Job intent updated id={} entity={} fields={}",
        job.id,
        new_plan.intent.entity_type,
        len(new_plan.intent.required_fields),
    )
    return job


@router.post(
    "/{job_id}/reparse",
    response_model=JobRead,
    summary="Edit prompt and re-parse plan",
)
async def reparse_job_prompt(
    job_id: UUID,
    payload: JobReparse,
    session: SessionDep,
    parser: ParserDep,
) -> Job:
    """Replace job prompt + parsed plan, and clear stale source candidates."""
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.status != JobStatus.PLANNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot re-parse prompt for job in status '{job.status.value}'; "
                "re-parse hanya boleh di 'planning'."
            ),
        )

    plan = await parser.parse(payload.prompt)
    await session.execute(delete(Source).where(Source.job_id == job.id))
    job.prompt = payload.prompt.strip()
    job.parsed_plan = plan.model_dump(mode="json")

    await session.commit()
    await session.refresh(job)

    logger.info(
        "Job prompt re-parsed id={} entity={} fields={}",
        job.id,
        plan.intent.entity_type,
        len(plan.intent.required_fields),
    )
    return job


@router.post(
    "/{job_id}/discover",
    response_model=JobRead,
    summary="Discover source candidates for a planning job",
)
async def discover_job_sources(
    job_id: UUID,
    session: SessionDep,
    discovery: DiscoveryDep,
    async_discovery: Annotated[bool, Query(alias="async")] = True,
) -> Job:
    """Isi `plan.sources` + tabel `sources` dengan kandidat URL.

    Default Phase 1.3b: enqueue Celery task dan push progress via WebSocket.
    `?async=false` tetap tersedia untuk deterministic smoke/integration tests.
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.status != JobStatus.PLANNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot discover sources for job in status '{job.status.value}'; "
                "source discovery hanya boleh di 'planning'."
            ),
        )
    if not job.parsed_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="job has no parsed plan; create or re-parse intent first",
        )

    if async_discovery:
        try:
            discover_sources_task.delay(str(job.id))
        except Exception as exc:  # pragma: no cover - broker transient fallback
            logger.warning("Failed to enqueue source discovery; running sync fallback: {}", exc)
        else:
            logger.info("Job source discovery queued id={}", job.id)
            return job

    plan = await discover_and_persist_sources(session=session, job=job, discovery=discovery)

    await session.commit()
    await session.refresh(job)

    logger.info(
        "Job sources discovered id={} sources={} estimated={}",
        job.id,
        len(plan.sources),
        plan.estimated_record_count,
    )
    return job


@router.patch(
    "/{job_id}/sources",
    response_model=JobRead,
    summary="Update source checklist selection",
)
async def update_job_sources(
    job_id: UUID,
    payload: JobSourcesUpdate,
    session: SessionDep,
) -> Job:
    """Persist user source checklist choices as `pending` / `skipped`."""
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.status != JobStatus.PLANNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot edit sources for job in status '{job.status.value}'; "
                "source edit hanya boleh di 'planning'."
            ),
        )
    if not job.parsed_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="job has no parsed plan; create or re-parse intent first",
        )

    selections_by_id = {selection.id: selection for selection in payload.sources}
    rows = (
        (
            await session.execute(
                select(Source)
                .where(Source.job_id == job.id, Source.id.in_(list(selections_by_id)))
                .order_by(Source.reliability_score.desc().nullslast(), Source.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if len(rows) != len(selections_by_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="one or more sources were not found for this job",
        )

    for row in rows:
        selection = selections_by_id[row.id]
        if row.status not in {SourceStatus.PENDING, SourceStatus.SKIPPED}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"source {row.id} cannot be edited in status '{row.status.value}'",
            )
        row.status = SourceStatus.PENDING if selection.enabled else SourceStatus.SKIPPED
        if selection.override_robots is not None:
            row.override_robots = selection.override_robots
        if row.status == SourceStatus.PENDING:
            row.last_error = None

    await session.flush()
    await _refresh_plan_sources(session=session, job=job)
    await session.commit()
    await session.refresh(job)

    logger.info("Job sources updated id={} changed={}", job.id, len(rows))
    return job


@router.post(
    "/{job_id}/run",
    response_model=JobRead,
    summary="Approve plan and start run",
)
async def run_job(
    job_id: UUID,
    session: SessionDep,
    async_run: Annotated[bool, Query(alias="async")] = True,
) -> Job:
    """Approve reviewed plan and move job into `running`.

    Phase 1.5 akan menambahkan scraper task yang mengkonsumsi run ini.
    Endpoint ini sengaja sudah membuat `runs` row agar kontrak FE/BE siap.
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.status != JobStatus.PLANNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot run job in status '{job.status.value}'.",
        )
    if not job.parsed_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="job has no parsed plan; create or re-parse intent first",
        )

    selected_source_count = (
        await session.execute(
            select(func.count())
            .select_from(Source)
            .where(Source.job_id == job.id, Source.status == SourceStatus.PENDING)
        )
    ).scalar_one()
    if selected_source_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Select at least one source before running this job.",
        )

    now = datetime.now(UTC)
    job.status = JobStatus.RUNNING
    job.started_at = now
    run = Run(
        job_id=job.id,
        trigger=RunTrigger.INITIAL,
        status=RunStatus.RUNNING,
        started_at=now,
    )
    session.add(run)
    await session.commit()
    await session.refresh(job)

    try:
        await publish_job_event(
            job_id=job.id,
            event_type="job_status",
            payload={
                "status": job.status.value,
                "run_id": str(run.id),
                "source_count": selected_source_count,
                "stage": "run_approved",
            },
        )
    except Exception as exc:  # pragma: no cover - redis transient
        logger.warning("Failed to publish run approval event job_id={}: {}", job.id, exc)

    if async_run:
        try:
            run_scrape_task.delay(str(job.id), str(run.id))
        except Exception as exc:  # pragma: no cover - broker transient fallback
            logger.warning("Failed to enqueue scrape task; running sync fallback: {}", exc)
        else:
            logger.info(
                "Job scrape queued id={} run_id={} sources={}",
                job.id,
                run.id,
                selected_source_count,
            )
            return job

    job = await scrape_job_sources(
        session=session,
        job_id=job.id,
        run_id=run.id,
        dispatcher=get_scraper_dispatcher(),
    )
    await session.commit()
    await session.refresh(job)

    logger.info(
        "Job run completed inline id={} run_id={} sources={}",
        job.id,
        run.id,
        selected_source_count,
    )
    return job


async def _refresh_plan_sources(*, session: AsyncSession, job: Job) -> Plan:
    """Refresh `job.parsed_plan.sources` from source rows."""
    if not job.parsed_plan:
        msg = "job has no parsed plan"
        raise ValueError(msg)
    plan = Plan.model_validate(job.parsed_plan)
    rows = (
        (
            await session.execute(
                select(Source)
                .where(Source.job_id == job.id)
                .order_by(Source.reliability_score.desc().nullslast(), Source.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    plan.sources = [source_row_to_plan(row) for row in rows]
    job.parsed_plan = plan.model_dump(mode="json")
    return plan
