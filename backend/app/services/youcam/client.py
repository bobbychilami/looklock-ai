"""Low-level HTTP client for the YouCam API (Perfect Corp).

INTEGRATION REFERENCE - every path and field used here is taken from the
official documentation at https://docs.makeupar.com. Nothing is guessed.

  Authentication (all v2 endpoints)
    Authorization: Bearer <API_KEY>          (BearerAuthenticationV2)

  Endpoints used by this scaffold
    POST /s2s/v2.0/file                       File Management
    POST /s2s/v2.0/task/skin-analysis         AI Skin Analysis v2.0
    GET  /s2s/v2.0/task/skin-analysis/{id}    AI Skin Analysis v2.0 status
    POST /s2s/v2.0/task/skin-tone-analysis    AI Facial Color Tones Analyzer
    GET  /s2s/v2.0/task/skin-tone-analysis/{id}
    POST /s2s/v2.0/task/cloth-v4              AI Clothes Virtual Try-On v4.0
    GET  /s2s/v2.0/task/cloth-v4/{id}
    GET  /s2s/v2.0/credit/feature-cost        Unit system (feature cost)

  Documented operational limits
    Rate limit      250 requests / 300 s, enforced per IP *and* per token.
    File retention  uploaded files and file_id valid 30 days.
    Task retention  task_id valid 30 days; result download URL valid 2 hours.
    Poll requirement tasks must be polled or they can expire as InvalidTaskId.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings
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
    FileCreateResponse,
    RunTaskResponse,
    TaskStatusResponse,
    YouCamErrorPayload,
)

logger = logging.getLogger(__name__)

USER_AGENT = "looklock-ai/0.1 (+hackathon prototype)"

# --- Documented endpoint paths --------------------------------------------- #
# https://docs.makeupar.com/develop/api_server
FILE_UPLOAD_PATH = "/s2s/v2.0/file"
FEATURE_COST_PATH = "/s2s/v2.0/credit/feature-cost"
SKIN_ANALYSIS_PATH = "/s2s/v2.0/task/skin-analysis"
SKIN_TONE_ANALYSIS_PATH = "/s2s/v2.0/task/skin-tone-analysis"
CLOTH_V4_PATH = "/s2s/v2.0/task/cloth-v4"

# Documented engine error codes, surfaced to the API layer as stable strings.
# Source: https://docs.makeupar.com/develop/error_codes
ENGINE_ERROR_MESSAGES: dict[str, str] = {
    "exceed_max_filesize": "The uploaded file is larger than the supported limit.",
    "invalid_parameter": "The request contained an invalid parameter.",
    "error_download_image": "YouCam could not download the source image.",
    "error_decode_image": "YouCam could not decode the source image.",
    "error_nsfw_content_detected": "NSFW content was detected in the image.",
    "error_no_face": "No face was detected. Try a clear, front-facing photo.",
    "error_pose": "Could not detect a pose in the source image.",
    "error_face_parsing": "Face segmentation failed on the source image.",
    "error_inference": "The YouCam inference pipeline reported an error.",
    "error_upload": "YouCam failed to upload the result image.",
    "error_multiple_people": "Multiple people detected; a single subject is required.",
    "error_multi_person": "Multiple people detected; a single subject is required.",
    "error_invalid_ref": (
        "The reference garment image was rejected. Use a clear front-facing "
        "garment photo with nothing obscuring it."
    ),
    "error_invalid_src": (
        "The source image was rejected. It must show more than the lower body "
        "or more than the feet."
    ),
    "error_apply_region_mismatch": (
        "The body region visible in your photo does not match the reference garment."
    ),
    "error_no_shoulder": "Shoulders are not visible in the image.",
    "error_large_face_angle": "The face angle in the image is too extreme.",
    # The docs contradict themselves here (AI Clothes File Specs say the long
    # side must be at least 128 px; the Error Codes page says 320 px). We avoid
    # asserting a number and let the engine's own message speak when present.
    "error_below_min_image_size": "Image is smaller than the minimum size YouCam accepts.",
    "error_face_position_invalid": "Face must be centered and fully visible.",
    "error_face_position_too_small": "The detected face is too small for analysis.",
    "error_face_position_out_of_boundary": "The face extends beyond the image edges.",
    "error_face_not_forward_facing": "Face must be looking directly at the camera.",
    "error_face_angle_upward": "Tilt your head slightly down.",
    "error_face_angle_downward": "Tilt your head slightly up.",
    "error_face_angle_leftward": "Turn your head slightly to the right.",
    "error_face_angle_rightward": "Turn your head slightly to the left.",
    "error_face_angle_left_tilt": "Straighten the left tilt of your head.",
    "error_face_angle_right_tilt": "Straighten the right tilt of your head.",
    "error_exceed_max_image_size": "The image exceeds the supported dimensions.",
    "unknown_internal_error": "YouCam reported an internal error.",
}

# Request validation errors returned by v2 task endpoints (HTTP 400).
RUN_ERROR_MESSAGES: dict[str, str] = {
    "InvalidParameters": "The YouCam request was rejected as invalid.",
    "CreditInsufficiency": "Not enough YouCam units remain for this request.",
    "InvalidStyleGroup": "The requested style group does not exist.",
    "InvalidStyle": "The requested style does not exist.",
    "BadRequest": "The YouCam request could not be processed.",
}


class YouCamClient:
    """Async HTTP client for the YouCam API server.

    One instance per process is created lazily and reused so connections are
    pooled. The API key lives only in memory on the backend.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._owns_transport = transport is None
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._upload_client: httpx.AsyncClient | None = None

    # -- lifecycle ---------------------------------------------------------- #

    @property
    def is_configured(self) -> bool:
        """True when an API key is present, i.e. an outbound call could work."""
        return self._settings.youcam_is_configured

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            if not self._settings.youcam_is_configured:
                raise YouCamNotConfiguredError
            kwargs: dict[str, Any] = {
                "base_url": self._settings.youcam_api_base_url.rstrip("/"),
                "timeout": httpx.Timeout(self._settings.youcam_timeout_seconds),
                "headers": {
                    "Authorization": f"Bearer {self._settings.youcam_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT,
                },
                "follow_redirects": True,
            }
            if self._transport is not None:
                kwargs["transport"] = self._transport
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def _get_upload_client(self) -> httpx.AsyncClient:
        """A second client with **no** default headers, for presigned uploads.

        Deliberately separate from :meth:`_get_client`. The upload target is a
        third-party storage host, not YouCam, so two things go wrong if the
        authenticated client is reused for it: the API key is handed to another
        organisation, and the extra headers invalidate the URL signature.
        """
        if self._upload_client is None:
            kwargs: dict[str, Any] = {
                "timeout": httpx.Timeout(self._settings.youcam_timeout_seconds),
                "headers": {"User-Agent": USER_AGENT},
                "follow_redirects": True,
            }
            if self._transport is not None:
                kwargs["transport"] = self._transport
            self._upload_client = httpx.AsyncClient(**kwargs)
        return self._upload_client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._upload_client is not None:
            await self._upload_client.aclose()
            self._upload_client = None

    async def __aenter__(self) -> YouCamClient:
        await self._get_client()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # -- request plumbing --------------------------------------------------- #

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.youcam_api_key}",
            "User-Agent": USER_AGENT,
        }
        if extra:
            headers.update(extra)
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        """Perform a JSON request with bounded retries.

        Retries only on 429 and 5xx. 429 honours `Retry-After` when present and
        otherwise uses exponential backoff with jitter, since the documented
        limit is a shared per-token bucket.
        """
        client = await self._get_client()
        request_headers = self._build_headers(headers)

        last_error: YouCamError | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.request(
                    method, path, json=json, params=params, headers=request_headers
                )
            except httpx.TimeoutException as exc:
                last_error = YouCamApiError(
                    f"YouCam request timed out: {exc}", status_code=504
                )
                if attempt == max_attempts:
                    raise last_error from exc
                await self._sleep_before_retry(None, attempt)
                continue
            except httpx.HTTPError as exc:
                last_error = YouCamApiError(
                    f"Could not reach the YouCam API: {exc}", status_code=502
                )
                if attempt == max_attempts:
                    raise last_error from exc
                await self._sleep_before_retry(None, attempt)
                continue

            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as exc:
                    raise YouCamApiError(
                        f"YouCam returned a non-JSON response: {exc}",
                        status_code=502,
                    ) from exc

            error = self._to_api_error(response)
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt == max_attempts:
                raise error
            last_error = error
            await self._sleep_before_retry(response, attempt)

        raise last_error or YouCamError("YouCam request failed.")

    async def _sleep_before_retry(
        self, response: httpx.Response | None, attempt: int
    ) -> None:
        delay = min(2.0 ** (attempt - 1), 8.0)
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                with contextlib.suppress(ValueError):
                    delay = max(delay, float(retry_after))
        await asyncio.sleep(delay + random.uniform(0, 0.3))

    def _to_api_error(self, response: httpx.Response) -> YouCamError:
        payload = YouCamErrorPayload.model_validate(_safe_json(response))
        code = payload.error_code
        message = payload.error or response.reason_phrase or "YouCam request failed"

        if response.status_code == 401:
            return YouCamAuthError(
                "YouCam rejected the API key. Verify YOUCAM_API_KEY is active.",
                status_code=401,
                error_code=code,
            )
        if response.status_code == 429:
            return YouCamRateLimitError()
        if code in RUN_ERROR_MESSAGES:
            message = RUN_ERROR_MESSAGES[code]
        return YouCamApiError(message, status_code=response.status_code, error_code=code)

    # -- public API --------------------------------------------------------- #

    async def get_feature_cost(self, page_size: int = 20) -> dict[str, Any]:
        """`GET /s2s/v2.0/credit/feature-cost` - unit cost per SKU.

        The AI Clothes documentation lists unit costs per engine version but does
        not include V4.0, so this endpoint is the only documented way to price
        the try-on we actually call.
        """
        return await self._request(
            "GET",
            FEATURE_COST_PATH,
            params={"page_size": page_size},
        )

    async def create_file_upload(
        self, *, file_name: str, file_size: int, content_type: str = "image/jpg"
    ) -> FileCreateResponse:
        """`POST /s2s/v2.0/file` - reserve a file slot and get an upload ticket.

        Calling this does NOT upload anything. Use the returned
        `requests[0].url` / `.method` / `.headers` to push the bytes.
        """
        payload = {
            "files": [
                {
                    "content_type": content_type,
                    "file_name": file_name,
                    "file_size": file_size,
                }
            ]
        }
        data = await self._request("POST", FILE_UPLOAD_PATH, json=payload)
        return FileCreateResponse.model_validate(data)

    async def upload_file_bytes(
        self,
        upload_url: str,
        content: bytes,
        headers: dict[str, str],
        method: str = "PUT",
    ) -> None:
        """Push raw bytes to the presigned URL returned by :meth:`create_file_upload`.

        The URL is signed for a specific method, URL and set of headers, so only
        what the vendor returned in `requests[].headers` may be sent, and the
        authenticated client is never used here.
        """
        upload_client = await self._get_upload_client()
        try:
            response = await upload_client.request(
                method.upper(),
                upload_url,
                content=content,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise YouCamApiError(
                f"Failed to upload image to YouCam storage: {exc}", status_code=502
            ) from exc
        if response.status_code >= 400:
            raise YouCamApiError(
                f"YouCam rejected the file upload (HTTP {response.status_code}).",
                status_code=response.status_code,
            )

    async def run_task(self, path: str, payload: dict[str, Any]) -> RunTaskResponse:
        """`POST /s2s/v2.0/task/{feature}` - start an async AI task, get a task_id."""
        data = await self._request("POST", path, json=payload)
        return RunTaskResponse.model_validate(data)

    async def run_cloth_v4(self, request: ClothV4TaskRequest) -> RunTaskResponse:
        """`POST /s2s/v2.0/task/cloth-v4` with the documented V4.0 body.

        `exclude_none` matters: the unset half of each id/url pair must be absent
        rather than present as `null`, otherwise the vendor sees a field its
        schema does not allow.
        """
        return await self.run_task(CLOTH_V4_PATH, request.model_dump(exclude_none=True))

    async def get_task_status(self, path: str, task_id: str) -> TaskStatusResponse:
        """`GET /s2s/v2.0/task/{feature}/{task_id}`."""
        data = await self._request("GET", f"{path}/{quote(task_id, safe='')}")
        return TaskStatusResponse.model_validate(data)

    async def await_task(
        self,
        path: str,
        task_id: str,
        *,
        on_status: Callable[[str], None] | None = None,
    ) -> TaskStatusResponse:
        """Poll a task until it reaches `success` or `error`.

        The docs require polling within the retention window, otherwise the task
        may expire as `InvalidTaskId` while units are still charged.

        `on_status` is called with each observed `data.task_status` so callers can
        surface progress; the callback is synchronous and must not block.
        """
        interval = self._settings.youcam_poll_interval_seconds
        budget = self._settings.youcam_poll_timeout_seconds
        waited = 0.0
        while True:
            response = await self.get_task_status(path, task_id)
            data = response.data
            state = data.task_status if data else None

            if state is not None and on_status is not None:
                on_status(state)

            if state == "success":
                return response
            if state == "error":
                code = data.error if data else None
                detail = (data.error_message if data else None) or ENGINE_ERROR_MESSAGES.get(
                    code or "", "YouCam could not process this image."
                )
                raise YouCamTaskError(detail, error_code=code)
            if state is None:
                raise YouCamError(
                    f"Unexpected task status response for task {task_id} "
                    f"(HTTP {response.status})."
                )

            if waited >= budget:
                raise YouCamTimeoutError(
                    f"Task {task_id} did not finish within {budget:.0f}s. "
                    "It keeps running upstream; retry the status lookup later."
                )
            await asyncio.sleep(interval)
            waited += interval


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        parsed = response.json()
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


_client: YouCamClient | None = None


def get_youcam_client() -> YouCamClient:
    """Process-wide singleton used as a FastAPI dependency."""
    global _client
    if _client is None:
        _client = YouCamClient()
    return _client


async def reset_youcam_client() -> None:
    """Close and drop the singleton (used on shutdown and in tests)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
