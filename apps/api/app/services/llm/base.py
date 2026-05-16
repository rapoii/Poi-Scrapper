"""Base protocol untuk semua LLM providers."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Generic LLM error (network, parsing, validation)."""


class LLMUnavailableError(LLMError):
    """Provider tidak ke-konfigurasi (no API key) atau di-disable."""


class LLMRateLimitError(LLMError):
    """Provider rate-limited; caller boleh fallback ke provider lain."""


class LLMProvider(Protocol):
    """Provider abstraction.

    Implementasi harus async + return Pydantic model yang di-validate.
    Pakai JSON Schema mode untuk reliable structured output.

    `name` & `model` dideklarasi sebagai read-only property supaya impl bebas
    memilih plain class attr atau computed @property (mis. FallbackProvider
    yang gabung beberapa providers).
    """

    @property
    def name(self) -> str:
        """Slug provider (mis. 'gemini', 'openrouter')."""
        ...

    @property
    def model(self) -> str:
        """Model name yang lagi dipakai (mis. 'gemini-2.0-flash')."""
        ...

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Call LLM, paksa output JSON yang match `response_schema`, return parsed instance.

        Raises:
          LLMUnavailableError: API key gak ada / provider gak siap.
          LLMRateLimitError: rate-limited (429); caller boleh retry/fallback.
          LLMError: generic failure (parse error, network).
        """
        ...
