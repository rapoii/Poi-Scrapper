"""Pytest fixtures untuk integration test backend.

Strategi: kita pakai database test ter-isolasi via transaction rollback.
Setiap test dibungkus transaction yang otomatis di-rollback. Tidak
butuh schema reset antar-test, tapi butuh schema sudah di-migrate
(`alembic upgrade head`) sebelum jalankan test integration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.session import get_session
from app.main import app
from app.services.intent_parser import StubIntentParser, get_intent_parser
from app.services.source_discovery import StubSourceDiscovery, get_source_discovery


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Session dengan auto-rollback supaya tiap test isolated."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with engine.connect() as conn:
        trans = await conn.begin()
        async with factory(bind=conn) as session:
            try:
                yield session
            finally:
                await trans.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client dengan FastAPI app + override session ke transaction-bound session."""

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_parser() -> StubIntentParser:
        return StubIntentParser()

    def _override_discovery() -> StubSourceDiscovery:
        return StubSourceDiscovery()

    app.dependency_overrides[get_session] = _override_session
    # Force stub parser di test supaya gak panggil Gemini real (network, tokens, flaky).
    app.dependency_overrides[get_intent_parser] = _override_parser
    app.dependency_overrides[get_source_discovery] = _override_discovery
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _quiet_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suppress Loguru output during tests untuk keep output bersih."""
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
