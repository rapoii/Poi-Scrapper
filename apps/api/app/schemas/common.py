"""Common Pydantic response shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """GET /health payload."""

    status: str = "ok"
    version: str
    app_env: str
    now: datetime
    db: dict[str, Any] = Field(default_factory=dict, description="Database reachability + latency")
    redis: dict[str, Any] = Field(default_factory=dict, description="Redis reachability + latency")


class ErrorResponse(BaseModel):
    """Unified error payload untuk client."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"error": "not_found", "message": "Job not found", "trace_id": "01JD..."}
        }
    )

    error: str
    message: str
    trace_id: str | None = None
    details: dict[str, Any] | None = None
