"""Error types raised by the YouCam service layer.

Routes translate these into HTTP responses; nothing from `httpx` escapes.
"""

from __future__ import annotations


class YouCamError(Exception):
    """Base class for all YouCam integration failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class YouCamNotConfiguredError(YouCamError):
    """No API key is configured on the backend."""

    def __init__(self) -> None:
        super().__init__(
            "YouCam API key is not configured. Set YOUCAM_API_KEY in the backend "
            "environment and restart the server."
        )


class YouCamApiError(YouCamError):
    """The vendor returned a non-success HTTP status."""

    def __init__(self, message: str, *, status_code: int, error_code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class YouCamAuthError(YouCamApiError):
    """HTTP 401 - the API key is missing, malformed, or inactive."""


class YouCamRateLimitError(YouCamApiError):
    """HTTP 429 - documented limit is 250 requests / 300 s per IP and per token."""

    def __init__(self, message: str = "YouCam rate limit exceeded") -> None:
        super().__init__(message, status_code=429, error_code="TooManyRequests")


class YouCamTaskError(YouCamError):
    """An AI task reached terminal state `error`.

    `error_code` is the documented engine code (e.g. `error_no_face`).
    """

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class YouCamTimeoutError(YouCamError):
    """Polling exceeded the configured budget before the task settled."""
