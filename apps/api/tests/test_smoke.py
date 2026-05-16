"""Phase 0 smoke tests — pastiin app bisa di-import + config resolv."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_import_main() -> None:
    assert app is not None


def test_config_loads() -> None:
    settings = get_settings()
    assert settings.app_env in {"development", "staging", "production"}
    assert settings.llm_provider in {"gemini", "groq", "openrouter", "openai", "anthropic"}


def test_version_endpoint() -> None:
    with TestClient(app) as client:
        resp = client.get("/version")
        assert resp.status_code == 200
        body = resp.json()
        assert "version" in body
        assert "app_env" in body
