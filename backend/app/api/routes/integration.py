"""YouCam integration status routes.

This router intentionally does NOT expose the AI pipeline yet. It publishes
only what a client needs to know before it can plan a request:

* whether the backend has an API key (so the UI can hide or explain features)
* which features are wired up
* where the boundaries of the integration still are

No response here contains the API key, and none of these routes makes an
outbound call unless explicitly named `diagnostics`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import settings_dependency
from app.core.config import Settings
from app.services.youcam.service import (
    FACE_ANGLE_STRICTNESS_LEVEL,
    FILTER_MULTI_PERSON,
    GARMENT_CATEGORIES,
    SKIN_ANALYSIS_FORMAT,
    SKIN_ANALYSIS_HD_ACTIONS,
)

router = APIRouter(prefix="/integration/ycam", tags=["integration"])


class FeatureStatus(BaseModel):
    name: str
    youcam_endpoint: str
    implemented: bool
    notes: str


class IntegrationStatusResponse(BaseModel):
    configured: bool
    api_base_url: str
    documentation: str
    features: list[FeatureStatus]
    open_items: list[str]


@router.get(
    "/status",
    response_model=IntegrationStatusResponse,
    summary="YouCam integration status",
)
async def integration_status(
    settings: Settings = Depends(settings_dependency),
) -> IntegrationStatusResponse:
    """Describe the current state of the YouCam integration.

    The base URL is safe to expose; the API key never is.
    """
    return IntegrationStatusResponse(
        configured=settings.youcam_is_configured,
        api_base_url=settings.youcam_api_base_url,
        documentation="https://docs.makeupar.com",
        features=[
            FeatureStatus(
                name="file_upload",
                youcam_endpoint="POST /s2s/v2.0/file",
                implemented=True,
                notes="Two-step flow: reserve the slot, then PUT bytes to the "
                "returned presigned URL to obtain a usable file_id.",
            ),
            FeatureStatus(
                name="skin_analysis",
                youcam_endpoint="POST /s2s/v2.0/task/skin-analysis",
                implemented=True,
                notes="Async task, polled to completion. Uses HD actions "
                f"{list(SKIN_ANALYSIS_HD_ACTIONS)} with format={SKIN_ANALYSIS_FORMAT}.",
            ),
            FeatureStatus(
                name="color_tone_analysis",
                youcam_endpoint="POST /s2s/v2.0/task/skin-tone-analysis",
                implemented=True,
                notes=f"Async task. face_angle_strictness_level="
                f"{FACE_ANGLE_STRICTNESS_LEVEL}.",
            ),
            FeatureStatus(
                name="apparel_virtual_try_on",
                youcam_endpoint="POST /s2s/v2.0/task/cloth-v4",
                implemented=True,
                notes=f"Async task. garment_category in {list(GARMENT_CATEGORIES)}; "
                f"filter_multi_person={FILTER_MULTI_PERSON}. Wired to "
                "POST /api/v1/integration/ycam/vto/test.",
            ),
            FeatureStatus(
                name="recommendation_look_generation",
                youcam_endpoint="n/a",
                implemented=False,
                notes="LOOKLOCK-owned. Not started: the product loop (looks, "
                "rationale, shop-this-look) is not built yet.",
            ),
        ],
        open_items=[
            "No product-loop endpoints exist yet (photo intake, look "
            "recommendations, rationale, shop-this-look breakdown).",
            "Reference garment images must be reachable publicly by URL or "
            "uploaded as file_ids; no catalog source is connected yet. Only the "
            "interface in app/catalog/product.py exists.",
            "The V4.0 try-on PoC keeps jobs in process memory. Nothing survives a "
            "restart, and result images are never stored.",
            "Result download URLs from YouCam expire after 2 hours; a cache or "
            "re-fetch strategy is not implemented.",
            "Unit cost for AI Clothes V4.0 is not published. V2.0 and V3.0 are "
            "documented as 2 units each; V4.0 must be read from "
            "GET /s2s/v2.0/credit/feature-cost.",
            "Webhook-based completion is documented as preferred but not "
            "configured; the client polls instead.",
            "Unit accounting is not surfaced to the UI yet.",
        ],
    )
