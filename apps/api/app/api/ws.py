"""WebSocket endpoints for live job events."""

from __future__ import annotations

import json
from uuid import UUID

import redis.asyncio as redis_async
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.config import get_settings
from app.services.job_events import build_job_event, job_events_channel

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/jobs/{job_id}")
async def job_events_ws(websocket: WebSocket, job_id: UUID) -> None:
    """Subscribe browser to Redis Pub/Sub events for one job."""
    await websocket.accept()

    settings = get_settings()
    redis = redis_async.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = job_events_channel(job_id)

    try:
        await pubsub.subscribe(channel)
        await websocket.send_json(
            build_job_event(
                job_id=job_id,
                event_type="log",
                payload={"stage": "ws_connected", "message": "Connected to job event stream."},
            )
        )
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            try:
                event = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                logger.warning("Invalid job event payload on {}: {}", channel, raw)
                continue
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected job_id={}", job_id)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.aclose()
