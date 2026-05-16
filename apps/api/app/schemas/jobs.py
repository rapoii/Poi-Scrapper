"""Pydantic schemas untuk endpoint /jobs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import JobStatus
from app.schemas.intent import Intent, Plan


class JobCreate(BaseModel):
    """Payload POST /jobs — user prompt natural language."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(
        min_length=4,
        max_length=4000,
        description="Prompt natural-language user, misal 'data dokter di RS Siloam Karawaci'",
    )


class JobReparse(BaseModel):
    """Payload POST /jobs/{id}/reparse — edit prompt + parse ulang plan."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(
        min_length=4,
        max_length=4000,
        description="Prompt revisi untuk mengganti intent dan reset source kandidat.",
    )


class JobRead(BaseModel):
    """Response shape untuk satu job (POST + GET by id)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    prompt: str
    parsed_plan: Plan | None
    status: JobStatus
    total_records: int
    avg_completeness: float | None
    avg_confidence: float | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobListItem(BaseModel):
    """Kolom subset untuk list (sidebar history)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prompt: str
    status: JobStatus
    total_records: int
    avg_completeness: float | None
    created_at: datetime
    finished_at: datetime | None


class JobListResponse(BaseModel):
    """GET /jobs payload."""

    items: list[JobListItem]
    total: int
    limit: int
    offset: int


class JobIntentUpdate(BaseModel):
    """Payload PATCH /jobs/{id}/intent — user-edited plan.

    User boleh edit fields, filters, scope, atau notes. Server akan re-validate
    via Pydantic + replace `parsed_plan.intent` (sources tetap di-pertahankan).
    """

    model_config = ConfigDict(extra="forbid")

    intent: Intent


class JobSourceSelection(BaseModel):
    """Satu item source checklist yang direview user."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    enabled: bool = True
    override_robots: bool | None = None


class JobSourcesUpdate(BaseModel):
    """Payload PATCH /jobs/{id}/sources."""

    model_config = ConfigDict(extra="forbid")

    sources: list[JobSourceSelection] = Field(min_length=1)
