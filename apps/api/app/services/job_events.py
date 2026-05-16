"""Job event publisher for WebSocket updates.

Redis Pub/Sub dipakai karena FastAPI dan Celery berjalan di proses berbeda.
Worker publish ke channel per job; WebSocket endpoint subscribe channel yang
sama lalu forward event JSON ke browser.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import redis.asyncio as redis_async

from app.core.config import get_settings

JobEventType = Literal[
    "job_status",
    "source_status",
    "record_upsert",
    "record_delete",
    "progress",
    "log",
    "error",
    "done",
]


def job_events_channel(job_id: str | UUID) -> str:
    """Redis Pub/Sub channel untuk satu job."""
    return f"poi:job:{job_id}:events"


def build_job_event(
    *,
    job_id: str | UUID,
    event_type: JobEventType,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build event shape matching `packages/shared/schema/ws_event.json`."""
    return {
        "type": event_type,
        "job_id": str(job_id),
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }


async def publish_job_event(
    *,
    job_id: str | UUID,
    event_type: JobEventType,
    payload: dict[str, Any] | None = None,
) -> None:
    """Publish one job event to Redis Pub/Sub."""
    settings = get_settings()
    client = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        event = build_job_event(job_id=job_id, event_type=event_type, payload=payload)
        await client.publish(job_events_channel(job_id), json.dumps(event))
    finally:
        await client.aclose()
