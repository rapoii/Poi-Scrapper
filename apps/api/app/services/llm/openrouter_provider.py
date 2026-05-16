"""OpenRouter provider — OpenAI-compatible Chat Completions API.

OpenRouter (`https://openrouter.ai/api/v1/chat/completions`) menerima format
sama dengan OpenAI Chat Completions. Untuk structured output kita pakai
`response_format: {"type": "json_object"}` + system prompt yang nunjukin
schema. Tidak semua model support `json_schema` strict mode — pakai json_object
sebagai common denominator.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError

from app.services.llm.base import (
    LLMError,
    LLMRateLimitError,
    LLMUnavailableError,
)

T = TypeVar("T", bound=BaseModel)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_TIMEOUT_S = 30.0


class OpenRouterProvider:
    """LLMProvider implementation untuk OpenRouter."""

    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        default_temperature: float = 0.2,
        default_max_tokens: int = 4096,
        http_referer: str = "https://poiscrapper.local",
        app_title: str = "PoiScrapper v3",
    ) -> None:
        if not api_key:
            msg = "OPENROUTER_API_KEY belum di-set"
            raise LLMUnavailableError(msg)
        self._api_key = api_key
        self.model = model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        # OpenRouter mewajibkan HTTP-Referer + X-Title untuk identitas app.
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": http_referer,
            "X-Title": app_title,
        }

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        # Tempel JSON schema ke system prompt supaya model paham bentuk output.
        json_schema = response_schema.model_json_schema()
        full_system = (
            f"{system_prompt}\n\n"
            "Output STRICTLY a single JSON object that conforms to this JSON Schema "
            "(no prose, no markdown fences, no explanation):\n\n"
            f"```json\n{json.dumps(json_schema, indent=2)}\n```"
        )

        body: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature if temperature is not None else self._default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._default_max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_S) as client:
                resp = await client.post(
                    f"{_OPENROUTER_BASE_URL}/chat/completions",
                    headers=self._headers,
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenRouter network error: {exc}") from exc

        if resp.status_code == 429:
            raise LLMRateLimitError(f"OpenRouter rate-limited: {resp.text[:200]}")
        if resp.status_code in {401, 403}:
            raise LLMUnavailableError(f"OpenRouter auth failed: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise LLMError(
                f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}",
            )

        try:
            payload = resp.json()
            content: str = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"OpenRouter unexpected response shape: {exc}") from exc

        # Beberapa model bungkus dengan ```json fence; coba unwrap.
        content = _strip_code_fence(content.strip())

        try:
            return response_schema.model_validate_json(content)
        except ValidationError as exc:
            logger.warning(
                "OpenRouter structured output failed schema validation: {}",
                exc.errors(include_url=False),
            )
            raise LLMError(f"Schema validation failed: {exc}") from exc


def _strip_code_fence(text: str) -> str:
    """Hapus markdown fence (```json ... ```) yang kadang dibungkusi model."""
    if text.startswith("```"):
        # Buang baris pertama (```json atau ```)
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
