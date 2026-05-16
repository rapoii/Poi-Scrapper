"""Pydantic schemas untuk API contracts.

Phase 0: schema API dasar (health, error).
Phase 1: + intent + plan + jobs.
"""

from app.schemas.common import ErrorResponse, HealthResponse
from app.schemas.intent import (
    Intent,
    IntentField,
    IntentFilter,
    Plan,
    PlanSourceDraft,
    TargetScope,
)
from app.schemas.jobs import JobCreate, JobListItem, JobListResponse, JobRead

__all__ = [
    "ErrorResponse",
    "HealthResponse",
    "Intent",
    "IntentField",
    "IntentFilter",
    "JobCreate",
    "JobListItem",
    "JobListResponse",
    "JobRead",
    "Plan",
    "PlanSourceDraft",
    "TargetScope",
]
