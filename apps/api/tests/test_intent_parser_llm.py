"""Tests untuk LLMIntentParser dengan fake provider.

Gak panggil Gemini real — kita inject fake provider yang return Intent
tertentu. Cover: cache hit/miss, schema validation, warning emission.
"""

from __future__ import annotations

from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from app.schemas.intent import Intent, IntentField, TargetScope
from app.services.intent_parser_llm import LLMIntentParser
from app.services.llm.base import LLMError

T = TypeVar("T", bound=BaseModel)


class FakeProvider:
    """LLMProvider stub yang return canned Intent."""

    name = "fake"
    model = "fake-1"

    def __init__(self, *, intent: Intent, raise_exc: Exception | None = None) -> None:
        self._intent = intent
        self._raise = raise_exc
        self.call_count = 0
        self.last_user_prompt: str | None = None

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        self.call_count += 1
        self.last_user_prompt = user_prompt
        if self._raise:
            raise self._raise
        # Cast: kita tahu test ini selalu pakai Intent.
        return self._intent  # type: ignore[return-value]


def _sample_intent() -> Intent:
    return Intent(
        entity_type="doctor",
        entity_label="Dokter Spesialis Jantung",
        target_scope=TargetScope(institution="RS Siloam", location="Karawaci"),
        required_fields=[
            IntentField(name="nama", data_type="string"),
            IntentField(name="spesialisasi", data_type="string"),
            IntentField(name="email", data_type="email", required=False),
        ],
        notes="Inferred from prompt",
    )


@pytest.mark.asyncio
async def test_parses_returns_plan_with_intent_and_no_sources() -> None:
    provider = FakeProvider(intent=_sample_intent())
    parser = LLMIntentParser(provider=provider, redis_client=None)

    plan = await parser.parse("data dokter spesialis jantung di RS Siloam")

    assert plan.intent.entity_type == "doctor"
    assert plan.intent.target_scope.institution == "RS Siloam"
    assert plan.sources == []
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_empty_prompt_raises() -> None:
    provider = FakeProvider(intent=_sample_intent())
    parser = LLMIntentParser(provider=provider, redis_client=None)

    with pytest.raises(ValueError, match="empty"):
        await parser.parse("   ")
    assert provider.call_count == 0


@pytest.mark.asyncio
async def test_provider_error_propagates() -> None:
    provider = FakeProvider(intent=_sample_intent(), raise_exc=LLMError("boom"))
    parser = LLMIntentParser(provider=provider, redis_client=None)

    with pytest.raises(LLMError):
        await parser.parse("any prompt")


@pytest.mark.asyncio
async def test_warns_when_entity_generic() -> None:
    provider = FakeProvider(
        intent=Intent(
            entity_type="generic",
            required_fields=[IntentField(name="nama", data_type="string")],
        ),
    )
    parser = LLMIntentParser(provider=provider, redis_client=None)

    plan = await parser.parse("vague prompt")
    assert plan.intent.entity_type == "generic"
    assert any("generic" in w.lower() or "tidak spesifik" in w.lower() for w in plan.warnings)


class _InMemoryRedis:
    """Redis-async-lookalike untuk test cache."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        self.set_calls += 1
        self._store[key] = value if isinstance(value, str) else str(value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.mark.asyncio
async def test_cache_hit_skips_provider_call() -> None:
    provider = FakeProvider(intent=_sample_intent())
    redis_fake = _InMemoryRedis()
    parser = LLMIntentParser(provider=provider, redis_client=redis_fake)  # type: ignore[arg-type]

    # First call: provider invoked, cache populated.
    await parser.parse("identical prompt")
    assert provider.call_count == 1
    assert redis_fake.set_calls == 1

    # Second call: cache hit, provider NOT invoked.
    await parser.parse("identical prompt")
    assert provider.call_count == 1, "Provider should not be called on cache hit"
    assert redis_fake.get_calls == 2  # GET called both times


@pytest.mark.asyncio
async def test_cache_key_differs_per_prompt() -> None:
    provider = FakeProvider(intent=_sample_intent())
    redis_fake = _InMemoryRedis()
    parser = LLMIntentParser(provider=provider, redis_client=redis_fake)  # type: ignore[arg-type]

    await parser.parse("prompt one")
    await parser.parse("prompt two")
    # Beda prompt → 2 cache entries, provider dipanggil 2x.
    assert provider.call_count == 2
    assert len(redis_fake._store) == 2
