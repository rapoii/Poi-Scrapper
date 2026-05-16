"""FallbackProvider — chain multiple LLM providers untuk resiliency.

Kalau primary provider rate-limited (429) atau unavailable (auth error),
otomatis lanjut ke provider berikutnya. Kalau semua gagal, raise error
terakhir.

Circuit breaker: setiap provider punya cooldown timestamp. Sekali kena 429
atau auth-fail, kita skip dia sampai cooldown expire — supaya request
berikutnya tidak ulang round-trip ke provider yang udah pasti gagal.
"""

from __future__ import annotations

import re
import time
from typing import TypeVar

from loguru import logger
from pydantic import BaseModel

from app.services.llm.base import (
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)

T = TypeVar("T", bound=BaseModel)

# Default cooldown saat 429 tanpa hint retry_delay.
_DEFAULT_COOLDOWN_S = 60.0
# Cap maksimum supaya transient blip gak bikin provider mati lama.
_MAX_RATE_LIMIT_COOLDOWN_S = 900.0  # 15 menit
# Auth fail (401/403) = config rusak; assume diperbaiki saat next deploy/restart.
_AUTH_FAIL_COOLDOWN_S = 24 * 3600.0


def _parse_retry_delay_seconds(exc: Exception) -> float | None:
    """Coba ekstrak retry-delay dari error message provider.

    Gemini: `'retryDelay': '11s'` atau `Please retry in 11.86s.`
    OpenRouter: kadang ada `Retry-After` header (gak ada di message).
    """
    text = str(exc)
    # Pattern 1: "retry in 12.3s"
    m = re.search(r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)\s*s", text, flags=re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Pattern 2: "'retryDelay': '11s'"
    m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?([0-9]+)s", text)
    if m:
        return float(m.group(1))
    return None


class FallbackProvider:
    """LLMProvider that routes ke next provider on retryable failures."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            msg = "FallbackProvider needs at least one provider"
            raise LLMUnavailableError(msg)
        self._providers = providers
        # Map provider id() → unix timestamp until which it's in cooldown.
        self._cooldown_until: dict[int, float] = {}

    @property
    def name(self) -> str:
        # Untuk logging cache key dst — pakai chain notation.
        return "+".join(p.name for p in self._providers)

    @property
    def model(self) -> str:
        return "+".join(p.model for p in self._providers)

    def _is_in_cooldown(self, provider: LLMProvider) -> float:
        """Return remaining cooldown seconds (>0) or 0 kalau ready."""
        until = self._cooldown_until.get(id(provider), 0.0)
        remaining = until - time.monotonic()
        return remaining if remaining > 0 else 0.0

    def _set_cooldown(self, provider: LLMProvider, seconds: float) -> None:
        capped = min(max(seconds, 1.0), _MAX_RATE_LIMIT_COOLDOWN_S)
        self._cooldown_until[id(provider)] = time.monotonic() + capped

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        last_exc: Exception | None = None
        skipped: list[tuple[str, str, float]] = []

        for idx, provider in enumerate(self._providers):
            cooldown_remaining = self._is_in_cooldown(provider)
            if cooldown_remaining > 0:
                skipped.append((provider.name, provider.model, cooldown_remaining))
                continue
            try:
                return await provider.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except LLMRateLimitError as exc:
                last_exc = exc
                delay = _parse_retry_delay_seconds(exc) or _DEFAULT_COOLDOWN_S
                self._set_cooldown(provider, delay)
                next_name = (
                    self._providers[idx + 1].name if idx + 1 < len(self._providers) else None
                )
                logger.warning(
                    "LLM {} ({}) rate-limited; cooldown {:.0f}s{}",
                    provider.name,
                    provider.model,
                    delay,
                    f" — fallback to {next_name}" if next_name else " — no more fallbacks",
                )
                continue
            except LLMUnavailableError as exc:
                last_exc = exc
                self._set_cooldown(provider, _AUTH_FAIL_COOLDOWN_S)
                logger.warning(
                    "LLM {} ({}) unavailable: {}; long cooldown",
                    provider.name,
                    provider.model,
                    exc,
                )
                continue

        if skipped:
            logger.debug(
                "Skipped {} provider(s) still in cooldown: {}",
                len(skipped),
                ", ".join(f"{n}({m}, {s:.0f}s)" for n, m, s in skipped),
            )

        if last_exc is None:
            # All providers in cooldown — surface as LLMUnavailableError.
            cooldowns = ", ".join(f"{n}({m}, {s:.0f}s)" for n, m, s in skipped) or "none"
            msg = f"All LLM providers in cooldown: {cooldowns}"
            raise LLMUnavailableError(msg)
        raise last_exc
