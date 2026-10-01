"""Feature-level YouCam operations used by the LOOKLOCK AI product loop.

Each method maps to one documented YouCam endpoint. The module is the seam
between our domain concepts (skin profile, virtual try-on) and the vendor's
transport, so a future API version change is contained here.

INTEGRATION REFERENCE: https://docs.makeupar.com
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import get_args

from app.services.youcam.client import (
    CLOTH_V4_PATH,
    SKIN_ANALYSIS_PATH,
    SKIN_TONE_ANALYSIS_PATH,
    YouCamClient,
    get_youcam_client,
)
from app.services.youcam.errors import YouCamError
from app.services.youcam.schemas import (
    ClothV4TaskRequest,
    FileDescriptor,
    GarmentCategory,
    MultiPersonFilter,
    SkinAnalysisScore,
    TaskStatusResponse,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CLOTH_V4_PATH",
    "FACE_ANGLE_STRICTNESS_LEVEL",
    "FILTER_MULTI_PERSON",
    "GARMENT_CATEGORIES",
    "MAX_IMAGE_BYTES",
    "SKIN_ANALYSIS_FORMAT",
    "SKIN_ANALYSIS_HD_ACTIONS",
    "SKIN_ANALYSIS_PATH",
    "SKIN_TONE_ANALYSIS_PATH",
    "ColorTones",
    "SkinProfile",
    "TryOnResult",
    "UploadedImage",
    "YouCamService",
    "get_youcam_service",
]

# --- AI Skin Analysis v2.0 ------------------------------------------------- #
# HD and SD actions cannot be mixed in one request, so LOOKLOCK uses one set.
# Chosen because these are the concerns that drive styling recommendations:
# texture and skin_type shape the "why this look" narrative, and moisture /
# oiliness / redness / radiance inform colourway choices.
# Source: https://docs.makeupar.com/reference/ai_skin_analysis/v2.0
SKIN_ANALYSIS_HD_ACTIONS: tuple[str, ...] = (
    "hd_skin_type",
    "hd_texture",
    "hd_oiliness",
    "hd_moisture",
    "hd_radiance",
    "hd_redness",
)

# `format=json` returns scores inline; `zip` returns a downloadable archive.
# LOOKLOCK uses json so no server-side unzip is needed.
SKIN_ANALYSIS_FORMAT = "json"

# --- AI Clothes Virtual Try-On v4.0 --------------------------------------- #
# Derived from the `GarmentCategory` literal transcribed from the V4 OpenAPI so
# the router, the request model and this module can never drift apart.
GARMENT_CATEGORIES: tuple[str, ...] = get_args(GarmentCategory)

# `off` lets the engine pick the largest person, which avoids false rejections
# on photos taken with friends. Documented default is also "off".
FILTER_MULTI_PERSON: MultiPersonFilter = "off"

# Documented default for `change_shoes`, which only applies to full_body and
# lower_body categories. Passed explicitly so the request we build is readable.
CHANGE_SHOES = True

# --- AI Facial Color Tones Analyzer ---------------------------------------- #
# strict | high | medium | low | flexible. Docs default to "high"; LOOKLOCK
# uses "medium" because user-uploaded photos are less controlled than a kiosk.
FACE_ANGLE_STRICTNESS_LEVEL = "medium"

# Documented image limits (https://docs.makeupar.com/reference/file): 10 MB for
# images. Enforced here so oversized uploads fail fast without burning units.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class UploadedImage:
    """An image that now lives in YouCam storage and has a `file_id`."""

    file_id: str


@dataclass(frozen=True)
class SkinProfile:
    """Normalised view of one AI Skin Analysis result."""

    scores: list[SkinAnalysisScore]
    raw: dict[str, object]

    def score_for(self, action: str, region: str | None = None) -> float | None:
        """Best matching `score` for an action, optionally scoped to a region."""
        candidates = [
            entry
            for entry in self.scores
            if entry.type == action and (region is None or entry.region == region)
        ]
        for entry in candidates:
            if entry.score is not None:
                return entry.score
            if entry.ui_score is not None:
                return float(entry.ui_score)
        return None


@dataclass(frozen=True)
class ColorTones:
    skin_color: str | None
    eye_color: str | None
    eye_color_name: str | None
    hair_color: str | None
    hair_color_name: str | None
    raw: dict[str, object]


@dataclass(frozen=True)
class TryOnResult:
    """A finished virtual try-on. `result_url` is valid for 2 hours."""

    task_id: str
    result_url: str


class YouCamService:
    """Domain-facing wrapper around the raw YouCam client."""

    def __init__(self, client: YouCamClient | None = None) -> None:
        self._client = client or get_youcam_client()

    @property
    def client(self) -> YouCamClient:
        return self._client

    @property
    def is_configured(self) -> bool:
        """True when the backend holds an API key, i.e. calls can be attempted."""
        return self._client.is_configured

    # -- file upload ------------------------------------------------------- #

    async def upload_image(
        self,
        content: bytes,
        *,
        file_name: str = "selfie.jpg",
        content_type: str = "image/jpg",
    ) -> UploadedImage:
        """Upload bytes through the two-step File API flow.

        Step 1 `POST /s2s/v2.0/file` reserves a slot and returns a presigned URL.
        Step 2 PUTs the bytes to that URL. `file_id` is only usable after step 2
        succeeds, which the docs call out explicitly.
        """
        if not content:
            raise YouCamError("The uploaded image is empty.")
        if len(content) > MAX_IMAGE_BYTES:
            raise YouCamError(
                f"Image is larger than the {MAX_IMAGE_BYTES // (1024 * 1024)} MB "
                "limit supported by YouCam."
            )

        created = await self._client.create_file_upload(
            file_name=file_name, file_size=len(content), content_type=content_type
        )
        descriptor: FileDescriptor | None = created.file
        if descriptor is None or not descriptor.file_id or not descriptor.requests:
            raise YouCamError(
                "YouCam did not return an upload target for the image file."
            )

        ticket = descriptor.requests[0]
        await self._client.upload_file_bytes(
            ticket.url, content, ticket.header_strings(), method=ticket.method
        )
        logger.info("Uploaded %s bytes to YouCam storage", len(content))
        return UploadedImage(file_id=descriptor.file_id)

    # -- skin analysis ------------------------------------------------------ #

    async def analyse_skin(self, file_id: str) -> SkinProfile:
        """Run AI Skin Analysis v2.0 and wait for the inline JSON scores."""
        submitted = await self._client.run_task(
            SKIN_ANALYSIS_PATH,
            {
                "src_file_id": file_id,
                "dst_actions": list(SKIN_ANALYSIS_HD_ACTIONS),
                "format": SKIN_ANALYSIS_FORMAT,
            },
        )
        task_id = submitted.task_id
        if task_id is None:
            raise YouCamError("YouCam did not return a task_id for skin analysis.")

        finished = await self._client.await_task(SKIN_ANALYSIS_PATH, task_id)
        return self._parse_skin_profile(finished)

    @staticmethod
    def _parse_skin_profile(response: TaskStatusResponse) -> SkinProfile:
        results = response.data.results if response.data else None
        return SkinProfile(
            scores=list(results.output) if results else [],
            raw=results.model_dump() if results else {},
        )

    # -- color tones -------------------------------------------------------- #

    async def analyse_color_tones(self, file_id: str) -> ColorTones:
        """Run the AI Facial Color Tones Analyzer for palette matching."""
        submitted = await self._client.run_task(
            SKIN_TONE_ANALYSIS_PATH,
            {
                "src_file_id": file_id,
                "face_angle_strictness_level": FACE_ANGLE_STRICTNESS_LEVEL,
            },
        )
        task_id = submitted.task_id
        if task_id is None:
            raise YouCamError("YouCam did not return a task_id for color tone analysis.")

        finished = await self._client.await_task(SKIN_TONE_ANALYSIS_PATH, task_id)
        results = finished.data.results if finished.data else None
        color = (results.color if results else None) or {}
        return ColorTones(
            skin_color=_as_str(color.get("skin_color")),
            eye_color=_as_str(color.get("eye_color")),
            eye_color_name=_as_str(color.get("eye_color_name")),
            hair_color=_as_str(color.get("hair_color")),
            hair_color_name=_as_str(color.get("hair_color_name")),
            raw=dict(color),
        )

# -- apparel virtual try-on --------------------------------------------- #

    async def submit_try_on_garment(
        self,
        *,
        source_file_id: str | None = None,
        source_url: str | None = None,
        reference_file_id: str | None = None,
        reference_url: str | None = None,
        garment_category: GarmentCategory = "auto",
        filter_multi_person: MultiPersonFilter = FILTER_MULTI_PERSON,
        change_shoes: bool = CHANGE_SHOES,
    ) -> str:
        """`POST /s2s/v2.0/task/cloth-v4` and return the `task_id`.

        Submission is separated from waiting so the UI can show the vendor task id
        as soon as it exists, and so a poll timeout does not hide it.

        Exactly one source and exactly one reference must be supplied; the request
        model enforces the documented `anyOf` rule before anything is sent.
        """
        request = ClothV4TaskRequest(
            src_file_id=source_file_id,
            src_file_url=source_url,
            ref_file_id=reference_file_id,
            ref_file_url=reference_url,
            garment_category=garment_category,
            filter_multi_person=filter_multi_person,
            change_shoes=change_shoes,
        )
        submitted = await self._client.run_cloth_v4(request)
        task_id = submitted.task_id
        if task_id is None:
            raise YouCamError("YouCam did not return a task_id for the try-on task.")
        logger.info("Submitted YouCam cloth-v4 task %s", task_id)
        return task_id

    async def await_try_on_garment(
        self, task_id: str, *, on_status: Callable[[str], None] | None = None
    ) -> TryOnResult:
        """Poll a cloth-v4 task and return the single result image URL.

        V4.0 returns one image, not an array, and the URL is a presigned object
        store link that the docs say is valid for 2 hours.
        """
        finished = await self._client.await_task(
            CLOTH_V4_PATH, task_id, on_status=on_status
        )
        results = finished.data.results if finished.data else None
        result_url = results.url if results else None
        if not result_url:
            raise YouCamError("YouCam finished the try-on without a result image URL.")
        return TryOnResult(task_id=task_id, result_url=result_url)

    async def try_on_garment(
        self,
        *,
        source_file_id: str,
        reference_file_id: str,
        garment_category: str = "auto",
    ) -> TryOnResult:
        """Run AI Clothes Virtual Try-On v4.0 end to end and wait for the result.

        `garment_category` must be one of :data:`GARMENT_CATEGORIES`; the request
        is rejected locally otherwise rather than burning a unit on a 400.
        """
        if garment_category not in GARMENT_CATEGORIES:
            raise YouCamError(
                f"Unknown garment_category '{garment_category}'. "
                f"Expected one of: {', '.join(GARMENT_CATEGORIES)}."
            )

        task_id = await self.submit_try_on_garment(
            source_file_id=source_file_id,
            reference_file_id=reference_file_id,
            garment_category=garment_category,  # type: ignore[arg-type]
        )
        return await self.await_try_on_garment(task_id)


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


_service: YouCamService | None = None


def get_youcam_service() -> YouCamService:
    """Process-wide singleton used as a FastAPI dependency."""
    global _service
    if _service is None:
        _service = YouCamService()
    return _service
