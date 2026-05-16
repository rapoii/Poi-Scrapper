"""Factory: pilih `LLMProvider` sesuai `settings.llm_provider` + auto-fallback.

Order resolusi:
  1. Build chain berdasarkan `settings.llm_provider` (primary) + provider lain
     yang punya API key valid (fallbacks).
  2. Kalau preferred + semua fallback nggak tersedia → raise LLMUnavailableError.
     Caller boleh handle (fallback ke stub parser).

Provider yang di-implement Phase 1.2: gemini, openrouter. Provider lain
(groq/openai/anthropic) bakal di-tambahin di Phase 2 / on-demand.
"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMProvider, LLMUnavailableError
from app.services.llm.fallback_provider import FallbackProvider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openrouter_provider import OpenRouterProvider

# Default model untuk Gemini primary (free tier).
_DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

# OpenRouter free models di-coba berurutan kalau yang sebelumnya 429.
# Sumber: https://openrouter.ai/models?q=:free (per 2025-Q4).
# Pilih model yang reliable JSON-mode + cukup capable untuk intent extraction.
_OPENROUTER_FREE_MODELS: tuple[str, ...] = (
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "deepseek/deepseek-v4-flash:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
)


def _build_gemini(settings: Settings, *, model: str | None = None) -> LLMProvider | None:
    if not settings.gemini_api_key:
        return None
    return GeminiProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=model or settings.llm_model or _DEFAULT_GEMINI_MODEL,
        default_temperature=settings.llm_temperature,
        default_max_tokens=settings.llm_max_tokens,
    )


def _build_openrouter(settings: Settings, *, model: str) -> LLMProvider | None:
    if not settings.openrouter_api_key:
        return None
    return OpenRouterProvider(
        api_key=settings.openrouter_api_key.get_secret_value(),
        model=model,
        default_temperature=settings.llm_temperature,
        default_max_tokens=settings.llm_max_tokens,
    )


def _build_chain(settings: Settings) -> LLMProvider:
    """Build provider chain dengan rotation antar model.

    Skema:
      - Primary = `settings.llm_provider` (`llm_model` dipakai sebagai model utama).
      - Setelah primary, coba semua provider lain yg punya API key + multi-model rotation.
      - OpenRouter dirotasi melalui `_OPENROUTER_FREE_MODELS` supaya tahan 429.
    """
    primary = settings.llm_provider
    chain: list[LLMProvider] = []

    # Primary
    if primary == "gemini":
        gp = _build_gemini(settings)
        if gp:
            chain.append(gp)
    elif primary == "openrouter":
        # Pakai model dari env (kalau di-set), kalau gak pakai item pertama dari rotasi.
        primary_model = settings.llm_model or _OPENROUTER_FREE_MODELS[0]
        op = _build_openrouter(settings, model=primary_model)
        if op:
            chain.append(op)

    # Fallback non-primary providers
    if primary != "gemini":
        gp = _build_gemini(settings, model=_DEFAULT_GEMINI_MODEL)
        if gp:
            chain.append(gp)

    # OpenRouter fallback rotation (skip model yg udah dipakai sebagai primary)
    if settings.openrouter_api_key:
        primary_or_model = settings.llm_model if primary == "openrouter" else None
        for model in _OPENROUTER_FREE_MODELS:
            if model == primary_or_model:
                continue
            op = _build_openrouter(settings, model=model)
            if op:
                chain.append(op)

    if not chain:
        msg = (
            "No LLM provider tersedia. Set GEMINI_API_KEY atau OPENROUTER_API_KEY "
            f"(provider preferred: {primary})."
        )
        raise LLMUnavailableError(msg)

    if len(chain) == 1:
        logger.info("LLM provider chain: {} ({})", chain[0].name, chain[0].model)
        return chain[0]

    chain_repr = " → ".join(f"{p.name}({p.model})" for p in chain)
    logger.info("LLM provider chain: {} (auto-fallback on 429 / auth)", chain_repr)
    return FallbackProvider(chain)


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Cached singleton — provider chain dibuat sekali saat startup."""
    return _build_chain(get_settings())
