"""Pydantic schemas for scraped records."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RecordRead(BaseModel):
    """One scraped record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    source_id: UUID | None
    data: dict[str, Any]
    field_confidences: dict[str, float] | None
    source_url: str
    completeness_score: float
    confidence_score: float
    fingerprint: str | None
    scraped_at: datetime
    deleted_at: datetime | None


class RecordListResponse(BaseModel):
    """GET /jobs/{job_id}/records payload."""

    items: list[RecordRead]
    total: int
    limit: int
    offset: int
