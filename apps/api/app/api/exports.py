"""Export endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Export, ExportFormat, Job, Record
from app.db.session import get_session
from app.services.export.csv import build_records_csv

router = APIRouter(prefix="/jobs/{job_id}/export", tags=["exports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", summary="Export scraped records")
async def export_job_records(
    job_id: UUID,
    session: SessionDep,
    export_format: Annotated[Literal["csv"], Query(alias="format")] = "csv",
) -> Response:
    """Export current non-deleted records for a job."""
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    if export_format != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format: {export_format}",
        )

    records = list(
        (
            await session.execute(
                select(Record)
                .where(Record.job_id == job.id, Record.deleted_at.is_(None))
                .order_by(Record.scraped_at.asc(), Record.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if not records:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No records available to export.",
        )

    payload = build_records_csv(job=job, records=records)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"poiscrapper-{str(job.id)[:8]}-{timestamp}.csv"
    export = Export(
        job_id=job.id,
        format=ExportFormat.CSV,
        column_map={"columns": payload.columns},
        file_url=f"inline://jobs/{job.id}/exports/{filename}",
        byte_size=len(payload.content),
        row_count=payload.row_count,
    )
    session.add(export)
    await session.commit()

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=payload.content,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )
