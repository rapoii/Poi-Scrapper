"""LLM-backed intent parser (Phase 1.2).

Pakai `LLMProvider` untuk parse prompt user → `Intent` (Pydantic model).
Hasil di-cache di Redis pakai SHA256(prompt) sebagai key supaya repeat prompt
tidak boros token.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import redis.asyncio as redis_async
from loguru import logger
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.intent import Intent, Plan
from app.services.llm import get_llm_provider
from app.services.llm.base import LLMError, LLMProvider, LLMUnavailableError

_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
_CACHE_KEY_PREFIX = "poi:intent:v1:"


SYSTEM_PROMPT = """\
You are an intent parser for a web scraping platform called PoiScrapper.

Given a user's natural-language prompt (Indonesian or English), extract a
structured `Intent` describing WHAT data they want to scrape and ABOUT WHICH
TARGET. Be precise, do not invent fields the user did not ask for, but also
infer obviously-relevant fields that any user of that entity type would expect
(e.g. for "doctors" infer name, specialty, contact; for "restaurants" infer
name, address, rating, cuisine).

Rules:
- `entity_type` must be a stable lowercase slug (e.g. "doctor", "restaurant",
  "school", "hotel", "company", "lawyer", "real_estate_listing").
- `entity_label` is a human-readable label (use the user's original phrasing,
  may include the institution / location).
- `target_scope.institution` is set when the prompt mentions a specific named
  organization ("RS Siloam Karawaci", "Universitas Indonesia"). Otherwise null.
- `target_scope.location` is set when the prompt mentions a city / region.
- `target_scope.country` defaults to "ID" for Indonesian prompts, "US" for
  US-context English, otherwise omit.
- `required_fields` should have 5-12 items. Use snake_case for `name`. Set
  `required: false` for fields that are nice-to-have but not core (e.g. social
  media links, photos).
- `data_type` must match one of the literal types defined in the schema.
- `filters` only when the user explicitly limits or excludes ("kecuali dokter
  umum", "rating above 4"). Map to `op` "not_contains" / "contains" / etc.
- `language` MUST match the actual prompt language: "id" for Indonesian,
  "en" for English.
- `output_format` defaults to "csv" unless user asks otherwise.
- `seed_urls`: only include URLs the user explicitly mentioned. Don't guess.
- `notes`: 1-2 sentence summary of how you interpreted the prompt.

Return STRICTLY a single JSON object matching the response schema. No prose.
"""


@dataclass
class LLMIntentParser:
    """Wraps an `LLMProvider` to produce `Plan` from natural-language prompts."""

    provider: LLMProvider
    redis_client: redis_async.Redis | None = None

    async def parse(self, prompt: str) -> Plan:
        cleaned = prompt.strip()
        if not cleaned:
            msg = "prompt is empty"
            raise ValueError(msg)

        cached = await self._get_cached(cleaned)
        if cached is not None:
            logger.debug(
                "Intent cache hit (provider={} model={})", self.provider.name, self.provider.model
            )
            return Plan(intent=cached, sources=[], warnings=[])

        intent = await self.provider.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=cleaned,
            response_schema=Intent,
        )

        await self._set_cached(cleaned, intent)

        warnings: list[str] = []
        if not intent.required_fields:
            warnings.append("LLM tidak menghasilkan required_fields; periksa prompt.")
        if intent.entity_type == "generic":
            warnings.append("Entity type tidak spesifik — pertimbangkan rephrase prompt.")

        return Plan(intent=intent, sources=[], warnings=warnings)

    # ---- caching ------------------------------------------------------------

    async def _get_cached(self, prompt: str) -> Intent | None:
        if self.redis_client is None:
            return None
        key = self._cache_key(prompt)
        try:
            raw = await self.redis_client.get(key)
        except Exception as exc:  # pragma: no cover - redis transient
            logger.warning("Redis cache GET failed: {}", exc)
            return None
        if raw is None:
            return None
        try:
            return Intent.model_validate_json(raw)
        except ValidationError:
            # Schema berubah → invalidate.
            await self.redis_client.delete(key)
            return None

    async def _set_cached(self, prompt: str, intent: Intent) -> None:
        if self.redis_client is None:
            return
        key = self._cache_key(prompt)
        try:
            await self.redis_client.set(
                key,
                intent.model_dump_json(),
                ex=_CACHE_TTL_SECONDS,
            )
        except Exception as exc:  # pragma: no cover - redis transient
            logger.warning("Redis cache SET failed: {}", exc)

    def _cache_key(self, prompt: str) -> str:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return f"{_CACHE_KEY_PREFIX}{self.provider.name}:{self.provider.model}:{digest}"


def build_llm_parser(
    settings: Settings | None = None,
    redis_client: redis_async.Redis | None = None,
) -> LLMIntentParser:
    """Construct LLMIntentParser. Caller bertanggung-jawab handle LLMUnavailableError."""
    s = settings or get_settings()
    provider = get_llm_provider()
    if redis_client is None:
        try:
            redis_client = redis_async.Redis.from_url(s.redis_url, decode_responses=True)
        except Exception as exc:  # pragma: no cover - misconfig
            logger.warning("Redis client init failed, intent cache disabled: {}", exc)
            redis_client = None
    return LLMIntentParser(provider=provider, redis_client=redis_client)


__all__ = [
    "LLMError",
    "LLMIntentParser",
    "LLMUnavailableError",
    "build_llm_parser",
]
