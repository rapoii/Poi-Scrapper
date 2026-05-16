"""Record read endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, Record
from app.db.session import get_session
from app.schemas.records import RecordListResponse, RecordRead

router = APIRouter(prefix="/jobs/{job_id}/records", tags=["records"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=RecordListResponse, summary="List scraped records for a job")
async def list_job_records(
    job_id: UUID,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RecordListResponse:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    where = (Record.job_id == job_id, Record.deleted_at.is_(None))
    total = (
        await session.execute(select(func.count()).select_from(Record).where(*where))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(Record)
                .where(*where)
                .order_by(Record.scraped_at.desc(), Record.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return RecordListResponse(
        items=[RecordRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
