"""Translate YouCam service exceptions into HTTP responses.

This is what keeps vendor details and credentials out of the browser while
still giving the UI actionable messages.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.image_validation import ImageValidationError
from app.services.youcam.errors import (
    YouCamApiError,
    YouCamAuthError,
    YouCamError,
    YouCamNotConfiguredError,
    YouCamRateLimitError,
    YouCamTaskError,
    YouCamTimeoutError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ImageValidationError)
    async def _bad_image(_: Request, exc: ImageValidationError) -> JSONResponse:
        # Raised before any vendor call, so this always costs nothing.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": str(exc), "error_code": "invalid_image"},
        )

    @app.exception_handler(YouCamNotConfiguredError)
    async def _not_configured(_: Request, exc: YouCamNotConfiguredError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": exc.message, "error_code": "youcam_not_configured"},
        )

    @app.exception_handler(YouCamAuthError)
    async def _auth_error(_: Request, exc: YouCamAuthError) -> JSONResponse:
        logger.error("YouCam authentication failure: %s", exc.message)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.message, "error_code": "youcam_auth_failed"},
        )

    @app.exception_handler(YouCamRateLimitError)
    async def _rate_limit(_: Request, exc: YouCamRateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "YouCam is rate limiting us. Try again in a few seconds.",
                "error_code": "youcam_rate_limited",
            },
        )

    @app.exception_handler(YouCamTimeoutError)
    async def _timeout(_: Request, exc: YouCamTimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": exc.message, "error_code": "youcam_timeout"},
        )

    @app.exception_handler(YouCamApiError)
    async def _api_error(_: Request, exc: YouCamApiError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(YouCamTaskError)
    async def _task_error(_: Request, exc: YouCamTaskError) -> JSONResponse:
        # Reached only for synchronous flows; the try-on PoC records these on the
        # job instead, because its route has already answered with 202.
        logger.info("YouCam task failed: %s (%s)", exc.message, exc.error_code)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(YouCamError)
    async def _generic(_: Request, exc: YouCamError) -> JSONResponse:
        logger.warning("YouCam integration error: %s", exc.message)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.message, "error_code": "youcam_error"},
        )
