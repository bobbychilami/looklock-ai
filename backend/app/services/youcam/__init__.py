"""YouCam API integration package.

Layering:
    client.py    raw HTTP, auth, retries, polling, error mapping
    service.py   feature-level operations (skin, colour, try-on)
    schemas.py   pydantic models transcribed from the published OpenAPI
    errors.py    exception types translated to HTTP by the API layer

The exact contract these implement is written up in
`docs/YOUTCAM_VTO_PROOF.md`.
"""

from app.services.youcam.client import (
    CLOTH_V4_PATH,
    FILE_UPLOAD_PATH,
    SKIN_ANALYSIS_PATH,
    SKIN_TONE_ANALYSIS_PATH,
    YouCamClient,
    get_youcam_client,
)
from app.services.youcam.errors import (
    YouCamApiError,
    YouCamAuthError,
    YouCamError,
    YouCamNotConfiguredError,
    YouCamRateLimitError,
    YouCamTaskError,
    YouCamTimeoutError,
)
from app.services.youcam.schemas import (
    ClothV4TaskRequest,
    GarmentCategory,
    MultiPersonFilter,
    TaskStatus,
)
from app.services.youcam.service import (
    GARMENT_CATEGORIES,
    MAX_IMAGE_BYTES,
    ColorTones,
    SkinProfile,
    TryOnResult,
    UploadedImage,
    YouCamService,
    get_youcam_service,
)

__all__ = [
    "CLOTH_V4_PATH",
    "FILE_UPLOAD_PATH",
    "GARMENT_CATEGORIES",
    "MAX_IMAGE_BYTES",
    "SKIN_ANALYSIS_PATH",
    "SKIN_TONE_ANALYSIS_PATH",
    "ClothV4TaskRequest",
    "ColorTones",
    "GarmentCategory",
    "MultiPersonFilter",
    "SkinProfile",
    "TaskStatus",
    "TryOnResult",
    "UploadedImage",
    "YouCamApiError",
    "YouCamAuthError",
    "YouCamClient",
    "YouCamError",
    "YouCamNotConfiguredError",
    "YouCamRateLimitError",
    "YouCamService",
    "YouCamTaskError",
    "YouCamTimeoutError",
    "get_youcam_client",
    "get_youcam_service",
]
