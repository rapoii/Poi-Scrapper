"""Source discovery service (Phase 1.3).

Tugas service ini: dari `Intent` yang sudah disetujui user, hasilkan kandidat
URL yang masuk akal untuk di-scrape. Implementasi utama memakai LLM provider
yang sama dengan intent parser; kalau LLM tidak tersedia atau sedang error,
fallback ke heuristic deterministic supaya UI tetap demo-able secara lokal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote_plus, urlparse

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.intent import Intent, ScrapeStrategyName
from app.services.llm import get_llm_provider
from app.services.llm.base import LLMError, LLMProvider, LLMUnavailableError

_MIN_SOURCE_CANDIDATES = 4
_MAX_SOURCE_CANDIDATES = 8


class SourceCandidate(BaseModel):
    """Kandidat source sebelum dipersist ke tabel `sources`."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=8)
    title: str | None = None
    domain: str | None = None
    strategy: ScrapeStrategyName = "static_html"
    reliability_score: float = Field(default=0.5, ge=0, le=1)
    reason: str | None = None


class SourceDiscoveryResult(BaseModel):
    """Output source discovery."""

    model_config = ConfigDict(extra="forbid")

    sources: list[SourceCandidate] = Field(default_factory=list)
    estimated_record_count: int | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)


class SourceDiscoveryProtocol(Protocol):
    """Dependency protocol untuk FastAPI + test override."""

    async def discover(self, intent: Intent) -> SourceDiscoveryResult:
        """Return source candidates for a parsed intent."""
        ...


SYSTEM_PROMPT = """\
You are a source discovery planner for PoiScrapper, a web scraping platform.

Given a structured scraping intent, suggest 3-6 likely source URLs that could
contain the requested records. Prefer official websites and dedicated directory
pages over generic search results. Use real, stable URLs when you know them.
If you are not sure a URL exists, still give the safest parent/domain URL and
lower the reliability_score.

Rules:
- Return only URLs that are publicly reachable without login as far as you know.
- Do not include social media unless it is the only plausible public source.
- `strategy` should be "static_html" unless the site is likely JS-heavy
  ("headless") or a public API ("api").
- `reliability_score` must reflect confidence from 0 to 1.
- Add a warning when sources are inferred from memory and should be verified.
- Return STRICTLY one JSON object matching the response schema. No prose.
"""


@dataclass
class LLMSourceDiscovery:
    """LLM-backed discovery with heuristic fallback."""

    provider: LLMProvider
    fallback: SourceDiscoveryProtocol

    async def discover(self, intent: Intent) -> SourceDiscoveryResult:
        try:
            result = await self.provider.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=intent.model_dump_json(),
                response_schema=SourceDiscoveryResult,
                temperature=0.1,
            )
        except LLMError as exc:
            logger.warning("LLM source discovery failed; fallback to heuristic: {}", exc)
            return await self.fallback.discover(intent)

        cleaned = _dedupe_candidates(result.sources)
        if not cleaned:
            fallback = await self.fallback.discover(intent)
            return SourceDiscoveryResult(
                sources=fallback.sources,
                estimated_record_count=result.estimated_record_count
                or fallback.estimated_record_count,
                warnings=[
                    *result.warnings,
                    "LLM tidak menghasilkan source valid; memakai heuristic fallback.",
                    *fallback.warnings,
                ],
            )

        fallback = await self.fallback.discover(intent)
        supplemented = _dedupe_candidates([*cleaned, *fallback.sources])
        if len(cleaned) < _MIN_SOURCE_CANDIDATES and len(supplemented) > len(cleaned):
            return SourceDiscoveryResult(
                sources=supplemented[:_MAX_SOURCE_CANDIDATES],
                estimated_record_count=result.estimated_record_count
                or fallback.estimated_record_count,
                warnings=[
                    *result.warnings,
                    (
                        "LLM hanya memberi sedikit source; sistem menambah kandidat "
                        "heuristic/search low-confidence untuk direview."
                    ),
                    *fallback.warnings,
                ],
            )

        return SourceDiscoveryResult(
            sources=cleaned[:_MAX_SOURCE_CANDIDATES],
            estimated_record_count=result.estimated_record_count,
            warnings=result.warnings
            or ["Source discovery berbasis LLM belum melakukan live verification."],
        )


class HeuristicSourceDiscovery:
    """Deterministic fallback yang tidak membutuhkan network/API key."""

    async def discover(self, intent: Intent) -> SourceDiscoveryResult:
        candidates: list[SourceCandidate] = []
        for raw_url in intent.seed_urls or []:
            url = _normalize_url(raw_url)
            if url:
                candidates.append(
                    _candidate(
                        url=url,
                        title="Seed URL dari prompt",
                        score=0.85,
                        reason="User explicitly provided this URL.",
                    )
                )

        entity = intent.entity_type.lower()
        scope = intent.target_scope
        institution = scope.institution if scope else None
        location = scope.location if scope else None
        country = (scope.country if scope else None) or ("ID" if intent.language == "id" else None)
        target = institution or location or intent.entity_label or entity
        query = " ".join(part for part in [intent.entity_label or entity, target, country] if part)

        candidates.extend(_entity_directory_candidates(entity, target, country))
        candidates.extend(
            _academic_candidates(entity=entity, target=target, query=query, country=country)
        )
        candidates.append(
            _candidate(
                url=f"https://www.google.com/search?q={quote_plus(query)}",
                title=f"Search results: {query}",
                score=0.35,
                reason="Fallback search URL when no verified directory is configured.",
            )
        )
        candidates.extend(_generic_search_candidates(query))

        cleaned = _dedupe_candidates(candidates)
        estimated = _estimate_count(entity=entity, has_narrow_scope=bool(institution))
        warnings = [
            "Source discovery memakai heuristic offline; verifikasi URL sebelum menjalankan scraper.",
            "Kandidat search low-confidence otomatis dibuat nonaktif supaya tidak langsung di-scrape.",
        ]
        return SourceDiscoveryResult(
            sources=cleaned[:_MAX_SOURCE_CANDIDATES],
            estimated_record_count=estimated,
            warnings=warnings,
        )


class StubSourceDiscovery:
    """Deterministic test double."""

    async def discover(self, intent: Intent) -> SourceDiscoveryResult:
        slug = _slug(intent.entity_type)
        return SourceDiscoveryResult(
            sources=[
                SourceCandidate(
                    url=f"https://example.com/{slug}",
                    title=f"Example {intent.entity_type} directory",
                    domain="example.com",
                    strategy="static_html",
                    reliability_score=0.6,
                    reason="Test fixture source.",
                )
            ],
            estimated_record_count=10,
            warnings=[],
        )


def get_source_discovery() -> SourceDiscoveryProtocol:
    """FastAPI dependency for source discovery."""

    heuristic = HeuristicSourceDiscovery()
    try:
        provider = get_llm_provider()
    except LLMUnavailableError as exc:
        logger.warning("LLM unavailable for source discovery; using heuristic: {}", exc)
        return heuristic
    return LLMSourceDiscovery(provider=provider, fallback=heuristic)


def _entity_directory_candidates(
    entity: str,
    target: str | None,
    country: str | None,
) -> list[SourceCandidate]:
    target_query = quote_plus(target or entity)
    is_id = country == "ID"

    if entity == "doctor":
        out = [
            _candidate("https://www.alodokter.com/cari-dokter", "Alodokter directory", 0.55),
            _candidate("https://www.halodoc.com/cari-dokter", "Halodoc directory", 0.52),
        ]
        if target and "siloam" in target.lower():
            out.insert(
                0,
                _candidate(
                    "https://www.siloamhospitals.com/en/find-a-doctor",
                    "Siloam Hospitals doctor search",
                    0.8,
                    strategy="headless",
                ),
            )
        return out

    if entity == "restaurant":
        return [
            _candidate(
                f"https://www.google.com/maps/search/{target_query}",
                "Google Maps restaurant search",
                0.48,
                strategy="headless",
            ),
            _candidate("https://www.tripadvisor.com/Restaurants", "Tripadvisor restaurants", 0.42),
        ]

    if entity == "hotel":
        return [
            _candidate(
                f"https://www.booking.com/searchresults.html?ss={target_query}",
                "Booking.com hotel search",
                0.5,
                strategy="headless",
            ),
            _candidate("https://www.tripadvisor.com/Hotels", "Tripadvisor hotels", 0.42),
        ]

    if entity == "school" and is_id:
        return [
            _candidate(
                "https://sekolah.data.kemdikbud.go.id/",
                "Kemdikbud school data",
                0.72,
            )
        ]

    if entity == "company":
        return [
            _candidate(
                f"https://www.google.com/maps/search/{target_query}",
                "Google Maps company search",
                0.42,
                strategy="headless",
            )
        ]

    return []


def _academic_candidates(
    *,
    entity: str,
    target: str | None,
    query: str,
    country: str | None,
) -> list[SourceCandidate]:
    haystack = " ".join(part.lower() for part in [entity, target or "", query] if part)
    if country != "ID" or not any(
        token in haystack
        for token in ["universitas", "mahasiswa", "student", "kampus", "faculty", "fakultas"]
    ):
        return []

    slug = _institution_slug(target or query)
    if not slug:
        return []

    out = [
        _candidate(
            f"https://www.{slug}.ac.id",
            f"Website resmi {target or slug}",
            0.62,
            reason="Inferred Indonesian university domain.",
        ),
        _candidate(
            f"https://{slug}.ac.id",
            f"Root domain {target or slug}",
            0.58,
            reason="Inferred Indonesian university root domain.",
        ),
    ]
    if any(token in haystack for token in ["hukum", "law", "fh", "fakultas hukum"]):
        out.append(
            _candidate(
                f"https://fh.{slug}.ac.id",
                f"Fakultas Hukum {target or slug}",
                0.56,
                reason="Inferred law faculty subdomain.",
            )
        )
    out.append(
        _candidate(
            f"https://www.google.com/search?q={quote_plus(f'site:{slug}.ac.id {query}')}",
            f"Search site:{slug}.ac.id",
            0.32,
            strategy="headless",
            reason="Low-confidence search URL for manual review.",
        )
    )
    return out


def _generic_search_candidates(query: str) -> list[SourceCandidate]:
    return [
        _candidate(
            f"https://www.bing.com/search?q={quote_plus(query)}",
            f"Bing search: {query}",
            0.3,
            strategy="headless",
            reason="Low-confidence search URL for manual review.",
        ),
        _candidate(
            f"https://duckduckgo.com/?q={quote_plus(query)}",
            f"DuckDuckGo search: {query}",
            0.28,
            strategy="headless",
            reason="Low-confidence search URL for manual review.",
        ),
    ]


def _institution_slug(value: str) -> str | None:
    lowered = value.lower()
    match = re.search(r"\(([^)]+)\)", lowered)
    if match:
        acronym = re.sub(r"[^a-z0-9]", "", match.group(1))
        if len(acronym) >= 3:
            return acronym

    known = {
        "universitas sultan ageng tirtayasa": "untirta",
        "untirta": "untirta",
    }
    for key, slug in known.items():
        if key in lowered:
            return slug
    return None


def _candidate(
    url: str,
    title: str,
    score: float,
    *,
    strategy: ScrapeStrategyName = "static_html",
    reason: str | None = None,
) -> SourceCandidate:
    return SourceCandidate(
        url=url,
        title=title,
        domain=_domain_from_url(url),
        strategy=strategy,
        reliability_score=score,
        reason=reason,
    )


def _normalize_url(raw_url: str) -> str | None:
    value = raw_url.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def _domain_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.netloc.lower() or None


def _dedupe_candidates(candidates: list[SourceCandidate]) -> list[SourceCandidate]:
    seen: set[str] = set()
    out: list[SourceCandidate] = []
    for candidate in candidates:
        url = _normalize_url(candidate.url)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(
            candidate.model_copy(
                update={
                    "url": url,
                    "domain": candidate.domain or _domain_from_url(url),
                }
            )
        )
    return out


def _estimate_count(*, entity: str, has_narrow_scope: bool) -> int:
    base = {
        "doctor": 30,
        "restaurant": 50,
        "hotel": 40,
        "school": 80,
        "company": 60,
    }.get(entity, 25)
    return max(5, base // 2) if has_narrow_scope else base


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "source"


__all__ = [
    "HeuristicSourceDiscovery",
    "LLMSourceDiscovery",
    "SourceCandidate",
    "SourceDiscoveryProtocol",
    "SourceDiscoveryResult",
    "StubSourceDiscovery",
    "get_source_discovery",
]
