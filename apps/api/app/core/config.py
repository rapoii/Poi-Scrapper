"""Settings singleton — dibaca dari environment variables / `.env` file.

Pakai Pydantic Settings v2 supaya type-safe & validated.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Master config. Baca `.env` di root workspace + env vars."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- General ----------
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    tz: str = "Asia/Jakarta"

    # ---------- API ----------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"
    api_cors_origins: str = "http://localhost:3000"

    # ---------- Database ----------
    database_url: str = Field(
        default="postgresql+asyncpg://poiscrapper:poiscrapper_dev@localhost:5432/poiscrapper",
        description="Async DSN for app runtime.",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://poiscrapper:poiscrapper_dev@localhost:5432/poiscrapper",
        description="Sync DSN khusus Alembic migrations.",
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ---------- Redis / Celery ----------
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ---------- LLM ----------
    llm_provider: Literal["gemini", "groq", "openrouter", "openai", "anthropic"] = "gemini"
    llm_model: str = "gemini-2.0-flash"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # ---------- Auth (Phase 2) ----------
    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None

    # ---------- Storage ----------
    storage_provider: Literal["local", "r2", "supabase"] = "local"
    storage_local_path: str = "./storage"

    # ---------- Scraping ----------
    scraper_default_timeout_ms: int = 30_000
    scraper_max_concurrency: int = 3
    respect_robots_txt: bool = True

    # ---------- Derived helpers ----------
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @field_validator("database_url", "database_url_sync", mode="before")
    @classmethod
    def _strip_whitespace(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Panggil dari mana saja."""
    return Settings()
