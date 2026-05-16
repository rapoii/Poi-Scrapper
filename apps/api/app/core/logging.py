"""Loguru-based structured logging + request-scoped trace_id."""

from __future__ import annotations

import contextvars
import logging
import sys
from types import FrameType
from typing import Any

from loguru import logger

from app.core.config import get_settings

# ---- Context vars -----------------------------------------------------------
_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)


def set_trace_id(value: str | None) -> None:
    _trace_id.set(value)


def get_trace_id() -> str | None:
    return _trace_id.get()


# ---- Loguru <-> stdlib bridge ----------------------------------------------
class InterceptHandler(logging.Handler):
    """Forward stdlib logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - plumbing
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _patcher(record: dict[str, Any]) -> None:
    record["extra"].setdefault("trace_id", get_trace_id() or "-")


def setup_logging() -> None:
    """Configure loguru + intercept stdlib logging. Idempotent."""
    settings = get_settings()
    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
        "<level>{level:<8}</level> "
        "<cyan>[{extra[trace_id]}]</cyan> "
        "<magenta>{name}</magenta>:<magenta>{function}</magenta>:<magenta>{line}</magenta> - "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=fmt,
        backtrace=settings.is_dev,
        diagnose=settings.is_dev,
        enqueue=False,
    )
    # Loguru's `Record` is a TypedDict; secara struktural kompatibel dengan
    # dict[str, Any] tapi mypy minta literal Record. Cast lewat ignore.
    logger.configure(patcher=_patcher)  # type: ignore[arg-type]

    # Forward stdlib logs (uvicorn, sqlalchemy, celery, etc.)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine", "celery"):
        logging.getLogger(noisy).handlers = [InterceptHandler()]
        logging.getLogger(noisy).propagate = False
