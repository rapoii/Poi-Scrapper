"""FastAPI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app import __version__
from app.api import api_router
from app.core.config import get_settings
from app.core.ids import new_id_str
from app.core.logging import get_trace_id, set_trace_id, setup_logging
from app.schemas.common import ErrorResponse


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    settings = get_settings()
    logger.info(
        "PoiScrapper API starting (v{}) env={} llm={}",
        __version__,
        settings.app_env,
        settings.llm_provider,
    )
    yield
    logger.info("PoiScrapper API stopping")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="PoiScrapper v3 API",
        version=__version__,
        description="Natural-language scraping orchestrator.",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url="/redoc" if settings.is_dev else None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        trace_id = request.headers.get("x-trace-id") or new_id_str()
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = get_trace_id()
        logger.opt(exception=exc).error(
            "Unhandled exception for {} {}", request.method, request.url.path
        )
        body = ErrorResponse(
            error="internal_error",
            message="Terjadi kesalahan internal. Silakan coba lagi.",
            trace_id=trace_id,
        )
        return JSONResponse(status_code=500, content=body.model_dump())

    app.include_router(api_router)
    return app


app = create_app()
