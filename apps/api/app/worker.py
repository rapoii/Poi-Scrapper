"""Celery app — shares codebase dengan FastAPI.

Jalankan worker dengan:

    uv run celery -A app.worker worker --loglevel=info --concurrency=2

Phase 0: Celery hanya di-setup supaya siap dipakai Phase 1.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()
_settings = get_settings()

celery_app = Celery(
    "poiscrapper",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=["app.tasks.source_discovery", "app.tasks.scrape"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=_settings.tz,
    enable_utc=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=60 * 60 * 24,  # 1 day
)


@celery_app.task(name="ping")
def ping() -> str:
    """Smoke test task: `celery -A app.worker call ping`."""
    return "pong"
