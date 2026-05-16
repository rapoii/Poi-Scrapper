"""Aggregate semua route module jadi satu `api_router`."""

from fastapi import APIRouter

from app.api import exports, health, jobs, records, ws

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(jobs.router)
api_router.include_router(records.router)
api_router.include_router(exports.router)
api_router.include_router(ws.router)
