"""Base types for scraper strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.db.models import ScrapeStrategy
from app.schemas.intent import Intent


@dataclass(frozen=True)
class ScrapedRecordDraft:
    """Record extracted from one source before DB insert."""

    data: dict[str, object]
    field_confidences: dict[str, float]
    source_url: str
    completeness_score: float
    confidence_score: float
    fingerprint: str


@dataclass(frozen=True)
class SourceWorkItem:
    """Immutable source snapshot safe to pass into concurrent scraper tasks."""

    id: UUID
    job_id: UUID
    url: str
    title: str | None
    reliability_score: float | None
    strategy: ScrapeStrategy
    override_robots: bool


class ScraperStrategyProtocol(Protocol):
    """Fetch + extract records for one source URL."""

    async def scrape(
        self,
        *,
        url: str,
        title: str | None,
        reliability_score: float | None,
        intent: Intent,
    ) -> list[ScrapedRecordDraft]:
        """Return extracted records."""
        ...
