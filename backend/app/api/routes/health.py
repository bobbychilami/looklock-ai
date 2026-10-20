"""Health and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app import __version__
from app.api.deps import settings_dependency
from app.catalog.service import get_product_source, provider_status_for
from app.core.config import Settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    youcam_configured: bool
    #: Which catalogue provider is selected, and whether it could answer. Names a
    #: provider, never a credential.
    catalog_provider_id: str
    catalog_provider_available: bool


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: Settings = Depends(settings_dependency)) -> HealthResponse:
    """    Liveness check.

    Deliberately never calls YouCam: a health probe must not consume units or
    fail because a third party is degraded. For the same reason it reports the
    catalogue provider's *configured* availability, never a live probe - that would
    spend a rate-limited search on every liveness tick.
    """
    provider = get_product_source(settings)
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        youcam_configured=settings.youcam_is_configured,
        catalog_provider_id=provider.info.id,
        catalog_provider_available=provider_status_for(provider).available,
    )


class ReadinessResponse(BaseModel):
    status: str
    youcam_configured: bool
    youcam_detail: str
    #: The catalogue provider's readiness, and the operator-facing reason when it
    #: has none. Setting names only - no values, no keys.
    catalog_provider_id: str
    catalog_provider_name: str
    catalog_provider_available: bool
    catalog_detail: str
    supports_shopping: bool
    #: Exact environment variable names still needed, e.g. `AMAZON_CLIENT_ID`.
    missing_settings: list[str]


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe for the configured integrations",
    status_code=status.HTTP_200_OK,
)
async def ready(settings: Settings = Depends(settings_dependency)) -> ReadinessResponse:
    """Reports whether the service can reach its integrations at all.

    Still no outbound call: it reports configuration state only. The real
    connectivity check lives behind the integration routes.

    Both integrations are reported here rather than in one aggregate `status`,
    because they fail for different reasons and are fixed by different people: a
    missing catalogue credential is an operator action, whereas a missing try-on
    key is a feature the app can run without.

    `status` stays degraded when *either* one is unusable. Narrowing it to the
    catalogue alone would make a deployment that promised virtual try-on report
    "ready" while try-on was dead, which is precisely the signal this probe exists
    to give. The configured catalogue provider reports its own availability, so a
    live provider that is selected but not yet credentialed shows up here too.
    """
    youcam_detail = (
        "YouCam API key is present."
        if settings.youcam_is_configured
        else "YOUCAM_API_KEY is not set; YouCam-backed features are disabled."
    )
    provider = get_product_source(settings)
    provider_info = provider.info
    provider_status = provider_status_for(provider)
    catalog_detail = (
        f"Serving live {provider_info.name} listings."
        if provider_status.available
        else f"No live catalogue available. {provider_status.reason}"
    )
    healthy = settings.youcam_is_configured and provider_status.available
    return ReadinessResponse(
        status="ready" if healthy else "degraded",
        youcam_configured=settings.youcam_is_configured,
        youcam_detail=youcam_detail,
        catalog_provider_id=provider_info.id,
        catalog_provider_name=provider_info.name,
        catalog_provider_available=provider_status.available,
        catalog_detail=catalog_detail,
        supports_shopping=provider_info.supports_shopping,
        missing_settings=list(settings.amazon_missing_settings),
    )
