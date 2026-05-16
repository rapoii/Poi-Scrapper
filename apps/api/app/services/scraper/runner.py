"""Job scraper runner."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Job, JobStatus, Record, Run, RunStatus, Source, SourceStatus
from app.schemas.intent import Plan
from app.services.job_events import publish_job_event
from app.services.scraper.base import ScrapedRecordDraft, SourceWorkItem
from app.services.scraper.dispatcher import ScraperDispatcher
from app.services.scraper.robots import check_robots_allowed
from app.services.scraper.static_html import NeedsHeadlessError
from app.services.source_persistence import merge_warnings, source_row_to_plan


@dataclass(frozen=True)
class SourceWorkResult:
    """Result of scraping one source, before DB persistence."""

    source_id: UUID
    status: SourceStatus
    drafts: list[ScrapedRecordDraft]
    error: str | None = None
    warning: str | None = None


async def scrape_job_sources(  # noqa: PLR0915
    *,
    session: AsyncSession,
    job_id: UUID,
    run_id: UUID,
    dispatcher: ScraperDispatcher,
) -> Job:
    """Scrape all pending sources for one job and update aggregate status."""
    job = await session.get(Job, job_id)
    run = await session.get(Run, run_id)
    if job is None:
        msg = f"job not found: {job_id}"
        raise ValueError(msg)
    if run is None:
        msg = f"run not found: {run_id}"
        raise ValueError(msg)
    if not job.parsed_plan:
        msg = f"job has no parsed plan: {job_id}"
        raise ValueError(msg)

    plan = Plan.model_validate(job.parsed_plan)
    sources = await _pending_sources(session=session, job_id=job.id)
    if not sources:
        await _mark_run_failed(job=job, run=run, message="no pending sources selected")
        return job

    source_rows_by_id = {source.id: source for source in sources}
    work_items = [_to_work_item(source) for source in sources]
    settings = get_settings()
    max_concurrency = max(1, settings.scraper_max_concurrency)
    semaphore = asyncio.Semaphore(max_concurrency)

    await _safe_publish(
        job_id=job.id,
        event_type="progress",
        payload={
            "stage": "scrape",
            "status": "started",
            "progress": 0.05,
            "source_count": len(sources),
            "max_concurrency": max_concurrency,
        },
    )
    await _mark_sources_running(session=session, job=job, sources=sources)

    added = 0
    failed = 0
    skipped = 0
    completed = 0
    warnings: list[str] = []
    confidence_scores: list[float] = []
    completeness_scores: list[float] = []

    tasks = [
        asyncio.create_task(
            _scrape_source(
                item=item,
                plan=plan,
                dispatcher=dispatcher,
                semaphore=semaphore,
                respect_robots_txt=settings.respect_robots_txt,
            )
        )
        for item in work_items
    ]

    for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
        result = await task
        source = source_rows_by_id[result.source_id]

        if result.warning:
            warnings.append(result.warning)
        if result.status == SourceStatus.SKIPPED:
            skipped += 1
            _apply_source_terminal_status(source=source, status=result.status, error=result.error)
        elif result.status == SourceStatus.FAILED:
            failed += 1
            _apply_source_terminal_status(source=source, status=result.status, error=result.error)
            logger.warning(
                "Source scrape failed source_id={} url={}: {}",
                source.id,
                source.url,
                result.error,
            )
        else:
            source_added = _add_records(
                session=session,
                job=job,
                source=source,
                drafts=result.drafts,
                confidence_scores=confidence_scores,
                completeness_scores=completeness_scores,
            )
            added += source_added
            _apply_source_terminal_status(source=source, status=SourceStatus.DONE, error=None)

        await _sync_plan_sources(session=session, job=job, extra_warnings=warnings)
        await session.flush()
        await _publish_source_result(job=job, source=source, result=result)
        await _safe_publish(
            job_id=job.id,
            event_type="progress",
            payload={
                "stage": "scrape",
                "status": "running",
                "progress": round(completed / len(sources), 3),
                "sources_done": completed,
                "source_count": len(sources),
                "records_added": added,
                "sources_failed": failed,
                "sources_skipped": skipped,
            },
        )

    await session.flush()
    total_records = (
        await session.execute(
            select(func.count()).select_from(Record).where(Record.job_id == job.id)
        )
    ).scalar_one()
    job.total_records = total_records
    job.avg_confidence = _avg(confidence_scores)
    job.avg_completeness = _avg(completeness_scores)
    job.finished_at = datetime.now(UTC)
    problem_count = failed + skipped
    job.status = (
        JobStatus.DONE
        if added > 0 and problem_count == 0
        else JobStatus.PARTIAL
        if added > 0
        else JobStatus.FAILED
    )

    run.records_added = added
    run.status = (
        RunStatus.DONE
        if job.status == JobStatus.DONE
        else RunStatus.PARTIAL
        if added > 0
        else RunStatus.FAILED
    )
    run.finished_at = job.finished_at
    await _sync_plan_sources(session=session, job=job, extra_warnings=warnings)

    await _safe_publish(
        job_id=job.id,
        event_type="done",
        payload={
            "stage": "scrape",
            "status": job.status.value,
            "record_count": total_records,
            "records_added": added,
            "sources_failed": failed,
            "sources_skipped": skipped,
        },
    )
    return job


async def _pending_sources(*, session: AsyncSession, job_id: UUID) -> list[Source]:
    return list(
        (
            await session.execute(
                select(Source)
                .where(Source.job_id == job_id, Source.status == SourceStatus.PENDING)
                .order_by(Source.reliability_score.desc().nullslast(), Source.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def _mark_run_failed(*, job: Job, run: Run, message: str) -> None:
    now = datetime.now(UTC)
    job.status = JobStatus.FAILED
    job.finished_at = now
    run.status = RunStatus.FAILED
    run.finished_at = now
    await _safe_publish(
        job_id=job.id,
        event_type="error",
        payload={"stage": "scrape", "message": message},
    )


async def _mark_sources_running(
    *,
    session: AsyncSession,
    job: Job,
    sources: list[Source],
) -> None:
    now = datetime.now(UTC)
    for source in sources:
        source.status = SourceStatus.RUNNING
        source.started_at = now
        source.last_error = None
        await _safe_publish(
            job_id=job.id,
            event_type="source_status",
            payload={"source_id": str(source.id), "status": source.status.value},
        )
    await _sync_plan_sources(session=session, job=job)
    await session.flush()


def _to_work_item(source: Source) -> SourceWorkItem:
    return SourceWorkItem(
        id=source.id,
        job_id=source.job_id,
        url=source.url,
        title=source.title,
        reliability_score=source.reliability_score,
        strategy=source.strategy,
        override_robots=source.override_robots,
    )


async def _scrape_source(
    *,
    item: SourceWorkItem,
    plan: Plan,
    dispatcher: ScraperDispatcher,
    semaphore: asyncio.Semaphore,
    respect_robots_txt: bool,
) -> SourceWorkResult:
    async with semaphore:
        decision = await check_robots_allowed(
            url=item.url,
            override=item.override_robots,
            respect_robots_txt=respect_robots_txt,
        )
        if not decision.allowed:
            return SourceWorkResult(
                source_id=item.id,
                status=SourceStatus.SKIPPED,
                drafts=[],
                error=decision.message,
            )

        warning = (
            f"{item.url}: robots.txt override aktif; scraper tetap lanjut."
            if decision.overridden
            else decision.message
        )
        try:
            scraper = dispatcher.for_strategy(item.strategy)
            try:
                drafts = await scraper.scrape(
                    url=item.url,
                    title=item.title,
                    reliability_score=item.reliability_score,
                    intent=plan.intent,
                )
            except NeedsHeadlessError:
                await _safe_publish(
                    job_id=item.job_id,
                    event_type="log",
                    payload={
                        "stage": "scrape",
                        "source_id": str(item.id),
                        "message": "Static HTML looked JS-rendered; retrying headless.",
                    },
                )
                drafts = await dispatcher.headless().scrape(
                    url=item.url,
                    title=item.title,
                    reliability_score=item.reliability_score,
                    intent=plan.intent,
                )
        except Exception as exc:
            return SourceWorkResult(
                source_id=item.id,
                status=SourceStatus.FAILED,
                drafts=[],
                error=str(exc),
                warning=warning,
            )

        return SourceWorkResult(
            source_id=item.id,
            status=SourceStatus.DONE,
            drafts=drafts,
            warning=warning,
        )


def _add_records(
    *,
    session: AsyncSession,
    job: Job,
    source: Source,
    drafts: list[ScrapedRecordDraft],
    confidence_scores: list[float],
    completeness_scores: list[float],
) -> int:
    added = 0
    for draft in drafts:
        record = Record(
            job_id=job.id,
            source_id=source.id,
            data=draft.data,
            field_confidences=draft.field_confidences,
            source_url=draft.source_url,
            completeness_score=draft.completeness_score,
            confidence_score=draft.confidence_score,
            fingerprint=draft.fingerprint,
            scraped_at=datetime.now(UTC),
        )
        session.add(record)
        added += 1
        confidence_scores.append(draft.confidence_score)
        completeness_scores.append(draft.completeness_score)
    return added


def _apply_source_terminal_status(
    *,
    source: Source,
    status: SourceStatus,
    error: str | None,
) -> None:
    source.status = status
    source.last_error = error
    source.finished_at = datetime.now(UTC)


async def _publish_source_result(
    *,
    job: Job,
    source: Source,
    result: SourceWorkResult,
) -> None:
    payload: dict[str, object] = {
        "source_id": str(source.id),
        "status": source.status.value,
    }
    if source.last_error:
        payload["error"] = source.last_error
    if result.warning:
        payload["warning"] = result.warning
    await _safe_publish(job_id=job.id, event_type="source_status", payload=payload)

    for draft in result.drafts:
        await _safe_publish(
            job_id=job.id,
            event_type="record_upsert",
            payload={
                "source_id": str(source.id),
                "record": {
                    "data": draft.data,
                    "source_url": draft.source_url,
                    "completeness_score": draft.completeness_score,
                    "confidence_score": draft.confidence_score,
                },
            },
        )


async def _sync_plan_sources(
    *,
    session: AsyncSession,
    job: Job,
    extra_warnings: list[str] | None = None,
) -> None:
    if not job.parsed_plan:
        return
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
    if extra_warnings:
        plan.warnings = merge_warnings(plan.warnings, extra_warnings)
    job.parsed_plan = plan.model_dump(mode="json")


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


async def _safe_publish(
    *,
    job_id: UUID,
    event_type: str,
    payload: dict[str, object],
) -> None:
    try:
        await publish_job_event(job_id=job_id, event_type=event_type, payload=payload)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover - redis transient
        logger.debug("Failed to publish job event job_id={} type={}: {}", job_id, event_type, exc)
