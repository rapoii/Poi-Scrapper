"""Pydantic models untuk Intent + scraping Plan.

Mengikuti contract di `packages/shared/schema/intent.json` + `plan.json`.
Phase 1: Intent dihasilkan oleh stub parser (rule-based) → Phase 1.2 Gemini.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DataType = Literal[
    "string",
    "number",
    "boolean",
    "date",
    "datetime",
    "url",
    "email",
    "phone",
    "array",
    "object",
]
FilterOp = Literal[
    "eq",
    "neq",
    "contains",
    "not_contains",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
]
OutputFormat = Literal["csv", "xlsx", "json"]
Language = Literal["id", "en"]
ScrapeStrategyName = Literal["static_html", "headless", "api", "pdf", "docx"]
SourceStatusName = Literal["pending", "running", "done", "failed", "skipped"]


class IntentField(BaseModel):
    """Satu kolom yang harus di-scrape per record."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, description="snake_case key untuk JSON record")
    label: str | None = Field(default=None, description="Display label untuk UI")
    data_type: DataType = "string"
    required: bool = True
    description: str | None = None


class IntentFilter(BaseModel):
    """Filter kondisi tambahan, ditampilkan ke user supaya transparan."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    op: FilterOp | None = None
    # `value` di-batasi ke string supaya kompatibel sama JSON Schema mode
    # LLM (`Any` gak bisa di-schema-kan secara strict). Untuk Phase 1, semua
    # filter value yang relevan memang string ("dokter umum", "rating 4+").
    value: str | None = None
    expression: str = Field(description="Frase original user, misal 'exclude dokter umum'")


class TargetScope(BaseModel):
    """Konteks target user, dipakai untuk source discovery + extraction prompt.

    Pakai `extra="ignore"` (bukan "allow") supaya `model_json_schema()` tidak
    emit `additionalProperties: true`, yang ditolak oleh Gemini structured-
    output API. Field tambahan boleh ditambah secara eksplisit di sini kalau
    perlu (mis. district, postal_code).
    """

    model_config = ConfigDict(extra="ignore")

    institution: str | None = None
    location: str | None = None
    country: str | None = None


class Intent(BaseModel):
    """Hasil parsing prompt user. Disimpan di `jobs.parsed_plan`."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = Field(min_length=1, description="Slug entity, misal 'doctor', 'restaurant'")
    entity_label: str | None = None
    target_scope: TargetScope = Field(default_factory=TargetScope)
    required_fields: list[IntentField] = Field(min_length=1)
    filters: list[IntentFilter] = Field(default_factory=list)
    output_format: OutputFormat = "csv"
    seed_urls: list[str] = Field(default_factory=list)
    language: Language = "id"
    notes: str | None = None


class PlanSourceDraft(BaseModel):
    """Source kandidat di plan (sebelum Source row dibuat di DB).

    Phase 1.3 source discovery akan mengisi list ini; Phase 1.1 boleh kosong.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    job_id: UUID | None = None
    url: str
    domain: str | None = None
    title: str | None = None
    strategy: ScrapeStrategyName = "static_html"
    reliability_score: float | None = Field(default=None, ge=0, le=1)
    status: SourceStatusName = "pending"
    override_robots: bool = False
    last_error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Plan(BaseModel):
    """Snapshot plan untuk preview ke user sebelum run di-trigger."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    sources: list[PlanSourceDraft] = Field(default_factory=list)
    estimated_record_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
