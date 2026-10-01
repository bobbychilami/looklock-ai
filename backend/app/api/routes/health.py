"""Health and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app import __version__
from app.api.deps import settings_dependency
from app.core.config import Settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    youcam_configured: bool


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: Settings = Depends(settings_dependency)) -> HealthResponse:
    """    Liveness check.

    Deliberately never calls YouCam: a health probe must not consume units or
    fail because a third party is degraded.
    """
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        youcam_configured=settings.youcam_is_configured,
    )


class ReadinessResponse(BaseModel):
    status: str
    youcam_configured: bool
    detail: str


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe for the YouCam integration",
    status_code=status.HTTP_200_OK,
)
async def ready(settings: Settings = Depends(settings_dependency)) -> ReadinessResponse:
    """Reports whether the service can talk to YouCam at all.

    Still no outbound call: it reports configuration state only. The real
    connectivity check lives behind the integration routes.
    """
    if settings.youcam_is_configured:
        return ReadinessResponse(
            status="ready",
            youcam_configured=True,
            detail="YouCam API key is present.",
        )
    return ReadinessResponse(
        status="degraded",
        youcam_configured=False,
        detail="YOUCAM_API_KEY is not set; YouCam-backed features are disabled.",
    )
