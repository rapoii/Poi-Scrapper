"""Tests untuk FallbackProvider — chain providers dengan auto-failover."""

from __future__ import annotations

from typing import TypeVar

import pytest
from pydantic import BaseModel

from app.services.llm.base import (
    LLMError,
    LLMRateLimitError,
    LLMUnavailableError,
)
from app.services.llm.fallback_provider import FallbackProvider, _parse_retry_delay_seconds

T = TypeVar("T", bound=BaseModel)


class _DummyResponse(BaseModel):
    value: str


class _ScriptedProvider:
    """Provider stub dengan scripted behavior (success/raise)."""

    def __init__(
        self,
        name: str,
        *,
        return_value: BaseModel | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.name = name
        self.model = f"{name}-model"
        self._return = return_value
        self._raise = raise_exc
        self.calls = 0

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        self.calls += 1
        if self._raise:
            raise self._raise
        if self._return is None:
            msg = "scripted provider has no return"
            raise RuntimeError(msg)
        return self._return  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_fallback_uses_first_when_first_succeeds() -> None:
    a = _ScriptedProvider("a", return_value=_DummyResponse(value="from-a"))
    b = _ScriptedProvider("b", return_value=_DummyResponse(value="from-b"))
    chain = FallbackProvider([a, b])

    result = await chain.generate_structured(
        system_prompt="sys",
        user_prompt="usr",
        response_schema=_DummyResponse,
    )
    assert result.value == "from-a"
    assert a.calls == 1
    assert b.calls == 0


@pytest.mark.asyncio
async def test_fallback_skips_to_next_on_rate_limit() -> None:
    a = _ScriptedProvider("a", raise_exc=LLMRateLimitError("429 quota"))
    b = _ScriptedProvider("b", return_value=_DummyResponse(value="from-b"))
    chain = FallbackProvider([a, b])

    result = await chain.generate_structured(
        system_prompt="sys",
        user_prompt="usr",
        response_schema=_DummyResponse,
    )
    assert result.value == "from-b"
    assert a.calls == 1
    assert b.calls == 1


@pytest.mark.asyncio
async def test_fallback_skips_on_unavailable() -> None:
    a = _ScriptedProvider("a", raise_exc=LLMUnavailableError("auth fail"))
    b = _ScriptedProvider("b", return_value=_DummyResponse(value="from-b"))
    chain = FallbackProvider([a, b])

    result = await chain.generate_structured(
        system_prompt="sys",
        user_prompt="usr",
        response_schema=_DummyResponse,
    )
    assert result.value == "from-b"


@pytest.mark.asyncio
async def test_fallback_does_not_skip_on_generic_error() -> None:
    """Generic LLMError = bug atau parse fail; jangan retry, raise immediately."""
    a = _ScriptedProvider("a", raise_exc=LLMError("schema validation fail"))
    b = _ScriptedProvider("b", return_value=_DummyResponse(value="from-b"))
    chain = FallbackProvider([a, b])

    with pytest.raises(LLMError, match="schema validation"):
        await chain.generate_structured(
            system_prompt="sys",
            user_prompt="usr",
            response_schema=_DummyResponse,
        )
    assert a.calls == 1
    assert b.calls == 0


@pytest.mark.asyncio
async def test_fallback_raises_last_when_all_fail() -> None:
    a = _ScriptedProvider("a", raise_exc=LLMRateLimitError("a-429"))
    b = _ScriptedProvider("b", raise_exc=LLMUnavailableError("b-401"))
    chain = FallbackProvider([a, b])

    with pytest.raises(LLMUnavailableError, match="b-401"):
        await chain.generate_structured(
            system_prompt="sys",
            user_prompt="usr",
            response_schema=_DummyResponse,
        )
    assert a.calls == 1
    assert b.calls == 1


def test_fallback_requires_at_least_one_provider() -> None:
    with pytest.raises(LLMUnavailableError):
        FallbackProvider([])


def test_fallback_name_combines_providers() -> None:
    a = _ScriptedProvider("gemini", return_value=_DummyResponse(value="x"))
    b = _ScriptedProvider("openrouter", return_value=_DummyResponse(value="y"))
    chain = FallbackProvider([a, b])
    assert chain.name == "gemini+openrouter"


@pytest.mark.asyncio
async def test_fallback_circuit_breaker_skips_cooled_provider() -> None:
    """Setelah 1 provider rate-limited, request kedua harus skip dia tanpa retry."""
    a = _ScriptedProvider("a", raise_exc=LLMRateLimitError("429 retry in 60s"))
    b = _ScriptedProvider("b", return_value=_DummyResponse(value="from-b"))
    chain = FallbackProvider([a, b])

    # First call: a fails, b succeeds.
    result = await chain.generate_structured(
        system_prompt="sys",
        user_prompt="usr",
        response_schema=_DummyResponse,
    )
    assert result.value == "from-b"
    assert a.calls == 1
    assert b.calls == 1

    # Second call: a is still in cooldown → skipped, b dipanggil lagi.
    result = await chain.generate_structured(
        system_prompt="sys",
        user_prompt="usr",
        response_schema=_DummyResponse,
    )
    assert result.value == "from-b"
    assert a.calls == 1, "Provider a should remain skipped during cooldown"
    assert b.calls == 2


@pytest.mark.asyncio
async def test_fallback_all_in_cooldown_raises_unavailable() -> None:
    a = _ScriptedProvider("a", raise_exc=LLMRateLimitError("a-429 retry in 60s"))
    b = _ScriptedProvider("b", raise_exc=LLMRateLimitError("b-429 retry in 60s"))
    chain = FallbackProvider([a, b])

    # First call: warm cooldowns by triggering each.
    with pytest.raises(LLMRateLimitError):
        await chain.generate_structured(
            system_prompt="sys",
            user_prompt="usr",
            response_schema=_DummyResponse,
        )
    assert a.calls == 1
    assert b.calls == 1

    # Second call: all providers cooled → LLMUnavailableError, no provider invocation.
    with pytest.raises(LLMUnavailableError, match="cooldown"):
        await chain.generate_structured(
            system_prompt="sys",
            user_prompt="usr",
            response_schema=_DummyResponse,
        )
    assert a.calls == 1
    assert b.calls == 1


def test_parse_retry_delay_supports_common_formats() -> None:
    assert _parse_retry_delay_seconds(Exception("Please retry in 11.86s.")) == 11.86
    assert _parse_retry_delay_seconds(Exception("'retryDelay': '11s'")) == 11.0
    assert _parse_retry_delay_seconds(Exception("retryDelay: '44s'")) == 44.0
    assert _parse_retry_delay_seconds(Exception("no hint here")) is None
