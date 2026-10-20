"""Product try-on: the shopper's photo plus a catalogue garment.

    POST /api/v1/tryon            -> 202 {job_id, phase, product_id}
    GET  /api/v1/tryon/{job_id}   -> phase progress, then the presigned result URL

This is the product-facing counterpart to the `/integration/ycam/vto/test`
endpoints, and it is deliberately thin. Both the photo and the reference garment
end up in the same four-step YouCam flow, so the job store, the phase machine and
the runner are reused rather than duplicated - a second implementation of the
orchestration would be a second thing to keep in step with the vendor.

The one genuinely new piece is resolving the reference: a catalogue garment is a
file inside this package, and YouCam cannot fetch a local path, so the asset is
read from disk and pushed through the File API like any other image. That reuses
the vendor's own upload path instead of inventing a way to hand it a URL that
would only be reachable from a developer's laptop.

Phases are the internal machine names. The UI maps them to shopper-facing
progress copy; see `PHASE_LABELS` in the frontend.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import youcam_service_dependency
from app.api.routes.tryon import RESULT_URL_TTL_HOURS
from app.catalog import Product, ProductNotFoundError, ProductSource, get_source, require_reference
from app.catalog.repository import tryon_asset_path
from app.core.image_validation import validate_image
from app.services.tryon import (
    TryOnJob,
    TryOnJobStore,
    TryOnReference,
    get_tryon_job_store,
    start_try_on_job,
)
from app.services.youcam.errors import YouCamNotConfiguredError
from app.services.youcam.schemas import MultiPersonFilter
from app.services.youcam.service import MAX_IMAGE_BYTES, YouCamService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tryon", tags=["tryon"])

#: Cap on the reference asset we are willing to read into memory. Bundled assets
#: are far smaller than this; the ceiling stops a mis-seeded catalogue from
#: turning a try-on into a large allocation.
MAX_REFERENCE_BYTES = MAX_IMAGE_BYTES


class TryOnAcceptedResponse(BaseModel):
    job_id: str
    phase: str
    product_id: str
    product_name: str
    poll_url: str


class TryOnStatusResponse(BaseModel):
    job_id: str
    phase: str
    product_id: str | None
    product_name: str | None
    filter_multi_person: str
    youcam_task_id: str | None
    youcam_task_status: str | None
    result_url: str | None
    result_url_expires_in_hours: int
    error: str | None
    error_code: str | None
    poll_url: str
    notes: list[str]


@router.post(
    "",
    response_model=TryOnAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Try one catalogue garment on the shopper's photo",
)
async def start_try_on(
    source_image: Annotated[UploadFile, File(description="Photo of the person")],
    product_id: Annotated[str, Form(description="Catalogue product to try on")],
    filter_multi_person: Annotated[MultiPersonFilter, Form()] = "off",
    service: YouCamService = Depends(youcam_service_dependency),
    store: TryOnJobStore = Depends(get_tryon_job_store),
    source: ProductSource = Depends(get_source),
) -> TryOnAcceptedResponse:
    """Validate the photo, resolve the garment, queue the job, return a job id.

    Order matters. The API key is checked first because without it nothing can
    succeed. The photo is validated second so a bad upload costs no vendor
    request. The catalogue is resolved last, so a typo in a product id does not
    make the shopper wait on a file upload.
    """
    if not service.is_configured:
        raise YouCamNotConfiguredError()

    photo_data = await source_image.read(MAX_IMAGE_BYTES + 1)
    await source_image.close()
    photo = validate_image(
        photo_data, label="your photo", declared_content_type=source_image.content_type
    )

    product = await source.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product with id {product_id!r} exists in this catalogue.",
        )

    try:
        reference = _resolve_reference(product)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # The catalogue declares the garment category, so the vendor is not asked to
    # guess. An item with no declared category falls back to `auto`, which the
    # V4.0 engine documents as auto-detecting from the reference image.
    garment_category = product.garment_category or "auto"

    job = store.create(
        garment_category=garment_category,
        filter_multi_person=filter_multi_person,
    )
    job.product_id = product.product_id
    job.product_name = product.name
    start_try_on_job(job, source=photo, reference=reference, service=service)
    logger.info("Queued product try-on %s for %s", job.job_id, product.product_id)

    return TryOnAcceptedResponse(
        job_id=job.job_id,
        phase=job.phase,
        product_id=product.product_id,
        product_name=product.name,
        poll_url=f"/api/v1/tryon/{job.job_id}",
    )


@router.get(
    "/{job_id}",
    response_model=TryOnStatusResponse,
    summary="Poll one product try-on",
)
async def get_try_on(
    job_id: str,
    store: TryOnJobStore = Depends(get_tryon_job_store),
) -> TryOnStatusResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "This try-on is unknown. It either expired or the backend restarted; "
                "nothing is persisted between runs."
            ),
        )
    return _to_response(job)


def _resolve_reference(product: Product) -> TryOnReference:
    """Resolve a product's garment to the transport YouCam expects.

    A live listing carries a public image `url` the vendor fetches itself; a
    product already in YouCam storage carries a `file_id`; only the bundled demo
    catalogue has a `local_path`, which has to be read from disk and pushed
    through the File API like any upload. A bundled asset is validated for the
    same reasons an upload is: it keeps the runner's contract uniform, and a
    corrupted or truncated file fails here with a clear log line instead of a
    vendor error.
    """
    reference = require_reference(product)
    if reference.file_id:
        return TryOnReference(file_id=reference.file_id)
    if reference.url:
        return TryOnReference(url=reference.url)

    path = tryon_asset_path(product)
    data = path.read_bytes()
    if len(data) > MAX_REFERENCE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This garment's reference image is unexpectedly large.",
        )
    image = validate_image(
        data,
        label="the reference garment",
        declared_content_type=reference.content_type or "image/png",
    )
    return TryOnReference(image=image)


def _to_response(job: TryOnJob) -> TryOnStatusResponse:
    notes = [
        "The result link is a presigned URL from YouCam and expires; "
        "we do not store the image.",
        "Try-on progress is kept in memory only and disappears on restart.",
    ]
    if job.result_url:
        notes.insert(0, f"This link stops working in about {RESULT_URL_TTL_HOURS} hours.")
    return TryOnStatusResponse(
        job_id=job.job_id,
        phase=job.phase,
        product_id=job.product_id,
        product_name=job.product_name,
        filter_multi_person=job.filter_multi_person,
        youcam_task_id=job.youcam_task_id,
        youcam_task_status=job.youcam_task_status,
        result_url=job.result_url,
        result_url_expires_in_hours=RESULT_URL_TTL_HOURS,
        error=job.error,
        error_code=job.error_code,
        poll_url=f"/api/v1/tryon/{job.job_id}",
        notes=notes,
    )


__all__ = ["TryOnAcceptedResponse", "TryOnStatusResponse", "router"]
