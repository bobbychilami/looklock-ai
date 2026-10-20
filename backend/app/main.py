"""FastAPI application factory.

Startup wires logging and CORS; shutdown disposes the shared HTTP client so
connections are not leaked under reload.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes import catalog, health, integration, look_tryon, tryon
from app.catalog.service import close_provider_state
from app.core.config import get_settings
from app.services.tryon import reset_tryon_jobs
from app.services.youcam.client import reset_youcam_client

API_PREFIX = "/api/v1"


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info(
        "%s started (env=%s, youcam_configured=%s)",
        settings.app_name,
        settings.app_env,
        settings.youcam_is_configured,
    )
    try:
        yield
    finally:
        await reset_tryon_jobs()
        await reset_youcam_client()
        await close_provider_state()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    from app import __version__ as version

    app = FastAPI(
        title=settings.app_name,
        version=version,
        description=(
            "Backend for LOOKLOCK AI. All YouCam API traffic is initiated here; "
            "the browser never receives YouCam credentials."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Accept"],
    )

    register_exception_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(integration.router, prefix=API_PREFIX)
    # The `/integration/ycam/vto` proof of concept. Kept intact and separate from
    # the product flow below, which reuses the same underlying service.
    app.include_router(tryon.router, prefix=API_PREFIX)
    app.include_router(catalog.router, prefix=API_PREFIX)
    app.include_router(look_tryon.router, prefix=API_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": f"{API_PREFIX}/health",
        }

    return app


app = create_app()
