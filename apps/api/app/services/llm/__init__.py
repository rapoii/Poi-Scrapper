"""LLM provider abstraction.

`LLMProvider` adalah interface yang harus di-implement tiap backend (Gemini /
OpenRouter / Groq / dll). `get_llm_provider()` factory pilih provider sesuai
`settings.llm_provider` + ketersediaan API key.
"""

from app.services.llm.base import (
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)
from app.services.llm.factory import get_llm_provider

__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMRateLimitError",
    "LLMUnavailableError",
    "get_llm_provider",
]
