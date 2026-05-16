"""Declarative base for all ORM models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.ids import new_id

# Consistent naming convention supaya alembic autogen deterministik.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """Base class untuk semua ORM models. AsyncAttrs membolehkan `await obj.awaitable_attrs.x`."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _now_utc() -> datetime:
    return datetime.now(UTC)


class UuidPkMixin:
    """Mixin: UUID primary key (ULID-based, time-sortable)."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)


class TimestampMixin:
    """Mixin: created_at + updated_at managed app-side (default + onupdate)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, onupdate=_now_utc, nullable=False
    )
