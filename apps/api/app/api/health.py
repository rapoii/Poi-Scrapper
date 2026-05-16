"""Health + version endpoints."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Liveness + dep check")
async def healthcheck(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """Return overall app + downstream status (db, redis)."""
    db_info = await _check_db(session)
    redis_info = await _check_redis(settings.redis_url)

    overall = "ok" if db_info.get("ok") and redis_info.get("ok") else "degraded"
    return HealthResponse(
        status=overall,
        version=__version__,
        app_env=settings.app_env,
        now=datetime.now(UTC),
        db=db_info,
        redis=redis_info,
    )


@router.get("/version", summary="App version + env")
async def version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"version": __version__, "app_env": settings.app_env}


# ---- Internal checks -------------------------------------------------------
# NOTE: Healthcheck dipanggil tiap ~10 detik dari FE. Kalau DB/Redis offline,
# kita log SATU BARIS (bukan full traceback) supaya terminal tidak banjir.
# Detail error tetap dikirim ke client di field `error` (truncated 200 char).
async def _check_db(session: AsyncSession) -> dict[str, object]:
    start = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("DB healthcheck failed: {} ({})", type(exc).__name__, str(exc)[:120])
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


async def _check_redis(url: str) -> dict[str, object]:
    start = time.perf_counter()
    redis: Redis | None = None
    try:
        redis = Redis.from_url(url, socket_connect_timeout=1.5, socket_timeout=1.5)
        pong = await redis.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"ok": bool(pong), "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("Redis healthcheck failed: {} ({})", type(exc).__name__, str(exc)[:120])
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        if redis is not None:
            await redis.aclose()
