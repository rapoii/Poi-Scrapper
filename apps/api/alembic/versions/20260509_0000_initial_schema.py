"""initial schema (users, jobs, sources, records, runs, exports)

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-09 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOTE: enum types di-create otomatis sama sa.Enum di tiap CREATE TABLE
    # (sekali per nama enum). Tidak perlu manual loop CREATE TYPE.

    # ---- users --------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("supabase_user_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_unique_constraint(
        "uq_users_supabase_user_id", "users", ["supabase_user_id"]
    )

    # ---- jobs ---------------------------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("parsed_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "planning", "running", "paused", "done", "failed", "partial",
                name="job_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_completeness", sa.Float(), nullable=True),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_jobs_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "avg_completeness IS NULL OR (avg_completeness BETWEEN 0 AND 1)",
            name="ck_jobs_avg_completeness_range",
        ),
        sa.CheckConstraint(
            "avg_confidence IS NULL OR (avg_confidence BETWEEN 0 AND 1)",
            name="ck_jobs_avg_confidence_range",
        ),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_user_created", "jobs", ["user_id", "created_at"])

    # ---- sources ------------------------------------------------------------
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column(
            "strategy",
            sa.Enum(
                "static_html", "headless", "api", "pdf", "docx",
                name="scrape_strategy",
            ),
            nullable=False,
            server_default="static_html",
        ),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "done", "failed", "skipped",
                name="source_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("override_robots", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_sources_job_id_jobs", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "reliability_score IS NULL OR (reliability_score BETWEEN 0 AND 1)",
            name="ck_sources_reliability_score_range",
        ),
    )
    op.create_index("ix_sources_job_id", "sources", ["job_id"])
    op.create_index("ix_sources_domain", "sources", ["domain"])
    op.create_index("ix_sources_status", "sources", ["status"])
    op.create_index("ix_sources_job_status", "sources", ["job_id", "status"])

    # ---- records ------------------------------------------------------------
    op.create_table(
        "records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("field_confidences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "completeness_score",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("fingerprint", sa.String(128), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_records_job_id_jobs", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_records_source_id_sources", ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "completeness_score BETWEEN 0 AND 1", name="ck_records_completeness_score_range"
        ),
        sa.CheckConstraint(
            "confidence_score BETWEEN 0 AND 1", name="ck_records_confidence_score_range"
        ),
    )
    op.create_index("ix_records_job_id", "records", ["job_id"])
    op.create_index("ix_records_source_id", "records", ["source_id"])
    op.create_index("ix_records_fingerprint", "records", ["fingerprint"])
    op.create_index("ix_records_job_fingerprint", "records", ["job_id", "fingerprint"])
    op.create_index("ix_records_job_scraped", "records", ["job_id", "scraped_at"])
    # GIN index untuk JSONB search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_records_data_gin ON records USING gin (data jsonb_path_ops)"
    )

    # ---- runs ---------------------------------------------------------------
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "trigger",
            sa.Enum(
                "initial", "manual_rerun", "scheduled",
                name="run_trigger",
            ),
            nullable=False,
            server_default="initial",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "running", "done", "failed", "partial",
                name="run_status",
            ),
            nullable=False,
            server_default="running",
        ),
        sa.Column("records_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("llm_tokens_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_runs_job_id_jobs", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_runs_job_id", "runs", ["job_id"])

    # ---- exports ------------------------------------------------------------
    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "format",
            sa.Enum("csv", "xlsx", "json", name="export_format"),
            nullable=False,
        ),
        sa.Column("column_map", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_exports_job_id_jobs", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_exports_job_id", "exports", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_exports_job_id", table_name="exports")
    op.drop_table("exports")

    op.drop_index("ix_runs_job_id", table_name="runs")
    op.drop_table("runs")

    op.execute("DROP INDEX IF EXISTS ix_records_data_gin")
    op.drop_index("ix_records_job_scraped", table_name="records")
    op.drop_index("ix_records_job_fingerprint", table_name="records")
    op.drop_index("ix_records_fingerprint", table_name="records")
    op.drop_index("ix_records_source_id", table_name="records")
    op.drop_index("ix_records_job_id", table_name="records")
    op.drop_table("records")

    op.drop_index("ix_sources_job_status", table_name="sources")
    op.drop_index("ix_sources_status", table_name="sources")
    op.drop_index("ix_sources_domain", table_name="sources")
    op.drop_index("ix_sources_job_id", table_name="sources")
    op.drop_table("sources")

    op.drop_index("ix_jobs_user_created", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    for enum_name in (
        "export_format",
        "run_status",
        "run_trigger",
        "scrape_strategy",
        "source_status",
        "job_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
