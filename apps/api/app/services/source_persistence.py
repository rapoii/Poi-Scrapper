"""Helpers to persist discovered source candidates onto a job plan."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, ScrapeStrategy, Source, SourceStatus
from app.schemas.intent import Plan, PlanSourceDraft
from app.services.source_discovery import SourceDiscoveryProtocol


async def discover_and_persist_sources(
    *,
    session: AsyncSession,
    job: Job,
    discovery: SourceDiscoveryProtocol,
) -> Plan:
    """Run source discovery and sync results into `sources` + `job.parsed_plan`."""
    if not job.parsed_plan:
        msg = "job has no parsed plan"
        raise ValueError(msg)

    plan = Plan.model_validate(job.parsed_plan)
    result = await discovery.discover(plan.intent)

    existing_rows = (
        (await session.execute(select(Source).where(Source.job_id == job.id))).scalars().all()
    )
    rows_by_url = {row.url: row for row in existing_rows}

    for candidate in result.sources:
        if candidate.url in rows_by_url:
            row = rows_by_url[candidate.url]
            if row.status == SourceStatus.PENDING:
                row.title = candidate.title or row.title
                row.domain = candidate.domain or row.domain
                row.strategy = ScrapeStrategy(candidate.strategy)
                row.reliability_score = candidate.reliability_score
            continue

        row = Source(
            job_id=job.id,
            url=candidate.url,
            domain=candidate.domain,
            title=candidate.title,
            strategy=ScrapeStrategy(candidate.strategy),
            reliability_score=candidate.reliability_score,
            status=_initial_source_status(candidate.reliability_score),
        )
        session.add(row)
        rows_by_url[candidate.url] = row

    await session.flush()

    all_rows = (
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
    plan.sources = [source_row_to_plan(row) for row in all_rows]
    if result.estimated_record_count is not None:
        plan.estimated_record_count = result.estimated_record_count
    plan.warnings = merge_warnings(plan.warnings, result.warnings)
    job.parsed_plan = plan.model_dump(mode="json")
    return plan


def source_row_to_plan(source: Source) -> PlanSourceDraft:
    """Convert ORM row to plan snapshot source."""
    return PlanSourceDraft(
        id=source.id,
        job_id=source.job_id,
        url=source.url,
        domain=source.domain,
        title=source.title,
        strategy=source.strategy.value,
        reliability_score=source.reliability_score,
        status=source.status.value,
        override_robots=source.override_robots,
        last_error=source.last_error,
        started_at=source.started_at,
        finished_at=source.finished_at,
    )


def _initial_source_status(reliability_score: float | None) -> SourceStatus:
    """Low-confidence search URLs should be reviewed before running."""
    if reliability_score is not None and reliability_score < 0.4:
        return SourceStatus.SKIPPED
    return SourceStatus.PENDING


def merge_warnings(existing: list[str], incoming: list[str]) -> list[str]:
    """Merge warning strings while preserving first-seen order."""
    seen: set[str] = set()
    merged: list[str] = []
    for warning in [*existing, *incoming]:
        if warning in seen:
            continue
        seen.add(warning)
        merged.append(warning)
    return merged
