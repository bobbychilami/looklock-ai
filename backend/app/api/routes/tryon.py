"""Virtual try-on proof-of-concept endpoints.

Shape of the flow exposed here:

    POST /integration/ycam/vto/test        -> 202 {job_id, phase}
    GET  /integration/ycam/vto/test/{id}   -> job progress, then the result URL
    GET  /integration/ycam/vto/options     -> the documented request enums

Why two calls instead of one blocking request: the vendor operation is
asynchronous and can take tens of seconds. Holding an HTTP connection open for
that would time out proxies and would leave the browser with no idea what is
happening. Returning a job id lets the UI show the real phases - uploading the
source image, uploading the reference image, submitting, polling - which is
exactly what a reviewer needs to see.

Nothing here is the final LOOKLOCK API. There is no account system, no catalog,
no result persistence and no webhooks.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import youcam_service_dependency
from app.core.image_validation import ValidatedImage, validate_image
from app.services.tryon import (
    PHASE_SEQUENCE,
    RESULT_URL_TTL_HOURS,
    TryOnJob,
    TryOnJobStore,
    TryOnReference,
    get_tryon_job_store,
    start_try_on_job,
)
from app.services.youcam.errors import YouCamNotConfiguredError
from app.services.youcam.schemas import GarmentCategory, MultiPersonFilter
from app.services.youcam.service import (
    GARMENT_CATEGORIES,
    MAX_IMAGE_BYTES,
    YouCamService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration/ycam/vto", tags=["integration"])

DOCUMENTATION = "https://docs.makeupar.com/reference/ai_clothes/section/overview"


class TryOnOptionsResponse(BaseModel):
    """Request vocabulary, straight from the V4.0 OpenAPI."""

    youcam_endpoint: str
    garment_categories: list[str]
    multi_person_filters: list[str]
    documentation: str
    max_image_bytes: int
    phases: list[str]
    notes: list[str]


class TryOnAcceptedResponse(BaseModel):
    """Returned immediately with 202; the work continues in the background."""

    job_id: str
    phase: str
    poll_url: str


class TryOnStatusResponse(BaseModel):
    job_id: str
    phase: str
    garment_category: str
    filter_multi_person: str
    youcam_task_id: str | None
    youcam_task_status: str | None
    result_url: str | None
    result_url_expires_in_hours: int
    error: str | None
    error_code: str | None
    poll_url: str
    notes: list[str]


@router.get(
    "/options",
    response_model=TryOnOptionsResponse,
    summary="Documented try-on request options",
)
async def try_on_options() -> TryOnOptionsResponse:
    """Expose the exact enums the submit endpoint accepts.

    The frontend builds its dropdowns from this so a value can never be offered
    in the UI that the backend would reject.
    """
    return TryOnOptionsResponse(
        youcam_endpoint="POST /s2s/v2.0/task/cloth-v4",
        garment_categories=list(GARMENT_CATEGORIES),
        multi_person_filters=["off", "normal", "strict"],
        documentation=DOCUMENTATION,
        max_image_bytes=MAX_IMAGE_BYTES,
        phases=list(PHASE_SEQUENCE),
        notes=[
            "V4.0 has no template_id variant, so a reference garment image is "
            "mandatory; both images are uploaded before the task is created.",
            "The documentation lists unit costs for V2.0 and V3.0 only. V4.0 must "
            "be priced via GET /s2s/v2.0/credit/feature-cost.",
            "The result URL is a presigned link that expires; nothing is stored.",
        ],
    )


@router.post(
    "/test",
    response_model=TryOnAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run one AI Clothes Virtual Try-On V4.0 proof of concept",
)
async def start_try_on_test(
    source_image: Annotated[UploadFile, File(description="Photo of the person")],
    reference_image: Annotated[
        UploadFile, File(description="Front-facing garment photo to try on")
    ],
    garment_category: Annotated[GarmentCategory, Form()] = "auto",
    filter_multi_person: Annotated[MultiPersonFilter, Form()] = "off",
    service: YouCamService = Depends(youcam_service_dependency),
    store: TryOnJobStore = Depends(get_tryon_job_store),
) -> TryOnAcceptedResponse:
    """Validate two images, queue the documented four-step flow, return a job id.

    Validation happens before any vendor call so a bad file costs nothing. The
    API key is checked first: without it the request cannot possibly succeed.
    """
    if not service.is_configured:
        raise YouCamNotConfiguredError()

    source = await _read_validated(source_image, label="your photo")
    reference = await _read_validated(reference_image, label="the garment photo")

    job = store.create(
        garment_category=garment_category,
        filter_multi_person=filter_multi_person,
    )
    start_try_on_job(
        job,
        source=source,
        reference=TryOnReference(image=reference),
        service=service,
    )
    logger.info("Queued try-on job %s (%s)", job.job_id, garment_category)

    return TryOnAcceptedResponse(
        job_id=job.job_id,
        phase=job.phase,
        poll_url=f"/api/v1/integration/ycam/vto/test/{job.job_id}",
    )


@router.get(
    "/test/{job_id}",
    response_model=TryOnStatusResponse,
    summary="Poll one try-on proof of concept",
)
async def get_try_on_test(
    job_id: str,
    store: TryOnJobStore = Depends(get_tryon_job_store),
) -> TryOnStatusResponse | JSONResponse:
    job = store.get(job_id)
    if job is None:
        # Returned as a response rather than raised so the shape stays close to a
        # real job, which keeps the client's error handling to one branch.
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "job_id": job_id,
                "phase": "failed",
                "error": (
                    "This try-on job is unknown. It either expired or the backend "
                    "restarted. Nothing is persisted between runs."
                ),
                "error_code": "tryon_job_not_found",
            },
        )
    return _to_response(job)


def _to_response(job: TryOnJob) -> TryOnStatusResponse:
    notes = [
        "Result URLs are presigned and expire; nothing is stored on our side.",
        "Jobs are kept in memory only and disappear when the backend restarts.",
    ]
    if job.result_url:
        notes.insert(
            0,
            f"This link stops working in about {RESULT_URL_TTL_HOURS} hours.",
        )
    return TryOnStatusResponse(
        job_id=job.job_id,
        phase=job.phase,
        garment_category=job.garment_category,
        filter_multi_person=job.filter_multi_person,
        youcam_task_id=job.youcam_task_id,
        youcam_task_status=job.youcam_task_status,
        result_url=job.result_url,
        result_url_expires_in_hours=RESULT_URL_TTL_HOURS,
        error=job.error,
        error_code=job.error_code,
        poll_url=f"/api/v1/integration/ycam/vto/test/{job.job_id}",
        notes=notes,
    )


async def _read_validated(upload: UploadFile, *, label: str) -> ValidatedImage:
    """Read an upload with a hard byte ceiling so a huge body cannot exhaust RAM."""
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    validated = validate_image(data, label=label, declared_content_type=upload.content_type)
    await upload.close()
    return validated