"""ORM models sesuai PRD §6 (users, jobs, sources, records, runs, exports).

Note: untuk Phase 1 kolom `user_id` di `jobs` boleh nullable supaya bisa jalan
single-user lokal tanpa auth; akan dijadikan NOT NULL di Phase 2.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UuidPkMixin


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Helper buat SQLAlchemy `Enum(values_callable=...)`.

    StrEnum default-nya ke-serialize pakai NAME (uppercase) sama SQLAlchemy.
    Postgres enum di-create dengan VALUE (lowercase) di migrasi awal kita,
    jadi kita override supaya pakai VALUE.
    """
    return [m.value for m in enum_cls]


# ============================================================================
# Enums
# ============================================================================
class JobStatus(enum.StrEnum):
    DRAFT = "draft"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"
    PARTIAL = "partial"


class SourceStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScrapeStrategy(enum.StrEnum):
    STATIC_HTML = "static_html"
    HEADLESS = "headless"
    API = "api"
    PDF = "pdf"
    DOCX = "docx"


class RunTrigger(enum.StrEnum):
    INITIAL = "initial"
    MANUAL_RERUN = "manual_rerun"
    SCHEDULED = "scheduled"


class RunStatus(enum.StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    PARTIAL = "partial"


class ExportFormat(enum.StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"


# ============================================================================
# Tables
# ============================================================================
class User(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Phase 2: link ke Supabase user.id
    supabase_user_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    jobs: Mapped[list[Job]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Job(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=_enum_values),
        default=JobStatus.DRAFT,
        nullable=False,
        index=True,
    )
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="jobs")
    sources: Mapped[list[Source]] = relationship(back_populates="job", cascade="all, delete-orphan")
    records: Mapped[list[Record]] = relationship(back_populates="job", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship(back_populates="job", cascade="all, delete-orphan")
    exports: Mapped[list[Export]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_user_created", "user_id", "created_at"),
        CheckConstraint(
            "avg_completeness IS NULL OR (avg_completeness BETWEEN 0 AND 1)",
            name="avg_completeness_range",
        ),
        CheckConstraint(
            "avg_confidence IS NULL OR (avg_confidence BETWEEN 0 AND 1)",
            name="avg_confidence_range",
        ),
    )


class Source(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    strategy: Mapped[ScrapeStrategy] = mapped_column(
        Enum(ScrapeStrategy, name="scrape_strategy", values_callable=_enum_values),
        default=ScrapeStrategy.STATIC_HTML,
        nullable=False,
    )
    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, name="source_status", values_callable=_enum_values),
        default=SourceStatus.PENDING,
        nullable=False,
        index=True,
    )
    override_robots: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship(back_populates="sources")

    __table_args__ = (
        Index("ix_sources_job_status", "job_id", "status"),
        CheckConstraint(
            "reliability_score IS NULL OR (reliability_score BETWEEN 0 AND 1)",
            name="reliability_score_range",
        ),
    )


class Record(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "records"

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    field_confidences: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship(back_populates="records")

    __table_args__ = (
        Index("ix_records_job_fingerprint", "job_id", "fingerprint"),
        Index("ix_records_job_scraped", "job_id", "scraped_at"),
        # GIN index untuk search ditambah di migrasi berikutnya (butuh op class jsonb_path_ops).
        CheckConstraint("completeness_score BETWEEN 0 AND 1", name="completeness_score_range"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence_score_range"),
    )


class Run(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "runs"

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger: Mapped[RunTrigger] = mapped_column(
        Enum(RunTrigger, name="run_trigger", values_callable=_enum_values),
        default=RunTrigger.INITIAL,
        nullable=False,
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", values_callable=_enum_values),
        default=RunStatus.RUNNING,
        nullable=False,
    )
    records_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    llm_tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship(back_populates="runs")


class Export(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "exports"

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat, name="export_format", values_callable=_enum_values), nullable=False
    )
    column_map: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    job: Mapped[Job] = relationship(back_populates="exports")
