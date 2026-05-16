"""Google Gemini provider via `google-genai` SDK.

Pakai `client.aio.models.generate_content` (async) + `response_schema` (Pydantic
model) untuk reliable structured output. Reference dokumentasi terbaru:
https://googleapis.github.io/python-genai/.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from loguru import logger
from pydantic import BaseModel, ValidationError

from app.services.llm.base import (
    LLMError,
    LLMRateLimitError,
    LLMUnavailableError,
)

T = TypeVar("T", bound=BaseModel)


# JSON Schema keywords yang tidak di-dukung Gemini structured output API.
# Reference: https://ai.google.dev/gemini-api/docs/structured-output
_GEMINI_UNSUPPORTED_KEYS = frozenset(
    {
        "additionalProperties",
        "$schema",
        "$id",
        "title",
        "examples",
        "default",
        "const",
        "patternProperties",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "uniqueItems",
        "contentEncoding",
        "contentMediaType",
    }
)


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    """Replace `$ref` references dengan inline definition (Gemini gak support refs)."""
    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str):
            ref = node["$ref"]
            # Format: "#/$defs/Foo"
            if ref.startswith("#/$defs/"):
                target_name = ref.split("/")[-1]
                target = defs.get(target_name)
                if target is None:
                    msg = f"Cannot resolve $ref {ref}"
                    raise LLMError(msg)
                return _inline_refs(deepcopy(target), defs)
        return {k: _inline_refs(v, defs) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def _strip_unsupported(node: Any) -> Any:
    """Recursive: hapus key JSON Schema yang gak di-support Gemini."""
    if isinstance(node, dict):
        return {
            k: _strip_unsupported(v) for k, v in node.items() if k not in _GEMINI_UNSUPPORTED_KEYS
        }
    if isinstance(node, list):
        return [_strip_unsupported(item) for item in node]
    return node


def _pydantic_to_gemini_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Generate Gemini-compatible JSON schema dict dari Pydantic model.

    Steps:
      1. Pydantic v2 emit JSON schema dengan `$defs` + `$ref`.
      2. Resolve semua `$ref` → inline.
      3. Strip key yang gak di-support (additionalProperties, title, dst).
    """
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    inlined = _inline_refs(raw, defs)
    sanitized = _strip_unsupported(inlined)
    if not isinstance(sanitized, dict):  # pragma: no cover - defensive
        msg = "Sanitized schema unexpectedly non-dict"
        raise LLMError(msg)
    return sanitized


class GeminiProvider:
    """LLMProvider implementation untuk Gemini Developer API."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.0-flash",
        default_temperature: float = 0.2,
        default_max_tokens: int = 4096,
    ) -> None:
        if not api_key:
            msg = "GEMINI_API_KEY belum di-set"
            raise LLMUnavailableError(msg)
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        # SDK auto-converter dari Pydantic emit `additionalProperties` & `$ref`
        # yang ditolak Gemini. Kita generate schema sendiri yang sudah di-sanitize.
        gemini_schema = _pydantic_to_gemini_schema(response_schema)
        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=gemini_schema,
            temperature=temperature if temperature is not None else self._default_temperature,
            max_output_tokens=max_tokens if max_tokens is not None else self._default_max_tokens,
        )

        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=config,
            )
        except genai_errors.ClientError as exc:
            # 429 = rate limit, 401/403 = auth → unavailable.
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if code == 429:
                raise LLMRateLimitError(str(exc)) from exc
            if code in {401, 403}:
                raise LLMUnavailableError(str(exc)) from exc
            raise LLMError(f"Gemini client error: {exc}") from exc
        except genai_errors.ServerError as exc:
            raise LLMError(f"Gemini server error: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise LLMError(f"Gemini unexpected error: {exc}") from exc

        text = (resp.text or "").strip()
        if not text:
            msg = "Gemini returned empty response"
            raise LLMError(msg)

        try:
            return response_schema.model_validate_json(text)
        except ValidationError as exc:
            logger.warning(
                "Gemini structured output failed schema validation: {}",
                exc.errors(include_url=False),
            )
            raise LLMError(f"Schema validation failed: {exc}") from exc
