"""Image validation applied before anything is sent to YouCam.

Two reasons this lives on our side of the wire:

1. The File API charges nothing, but a task submission does burn units, and the
   documented engine limits are 10 MB per image with jpg/png formats. Catching
   an oversized or non-image payload locally is free.
2. A multipart upload's `Content-Type` header is attacker-controlled. Sniffing
   the leading bytes means the format we declare to YouCam is derived from the
   actual payload rather than from the request metadata.

Reference: https://docs.makeupar.com/reference/file (File Specs & Errors).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.youcam.service import MAX_IMAGE_BYTES

# Documented: "Images: The file size should be less than 10MB", jpg / png only.
ALLOWED_IMAGE_CONTENT_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/jpg", "image/png"}
)

#: Content type to send YouCam for each sniffed format.
CANONICAL_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "image/jpg",
    "image/png": "image/png",
}

#: File extension used when we build a file name for the File API, keyed by the
#: canonical content type above. We never forward a user-supplied file name, so
#: this cannot carry path separators or shell metacharacters.
EXTENSIONS: dict[str, str] = {
    "image/jpg": ".jpg",
    "image/png": ".png",
}

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ImageValidationError(ValueError):
    """A rejected upload. The API layer turns this into a 422."""


@dataclass(frozen=True)
class ValidatedImage:
    """Bytes that passed every local check, ready to hand to the File API."""

    data: bytes
    content_type: str
    size_bytes: int


def sniff_image_content_type(data: bytes) -> str | None:
    """Return the image content type implied by the leading bytes, if any.

    Only JPEG and PNG are recognised because those are the only formats the
    documentation lists for images.
    """
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    return None


def validate_image(
    data: bytes,
    *,
    label: str,
    declared_content_type: str | None = None,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> ValidatedImage:
    """Check size and format, returning normalised bytes.

    Args:
        data: the raw upload payload.
        label: human name used in error messages, e.g. "your photo".
        declared_content_type: what the multipart request claimed, if anything.
        max_bytes: the documented per-image limit.
    """
    if not data:
        raise ImageValidationError(f"No data was received for {label}.")

    if len(data) > max_bytes:
        limit_mb = max_bytes / (1024 * 1024)
        raise ImageValidationError(
            f"{label.capitalize()} is {len(data) / (1024 * 1024):.1f} MB. "
            f"YouCam accepts at most {limit_mb:.0f} MB per image."
        )

    declared = (declared_content_type or "").split(";")[0].strip().lower()
    if declared and declared not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ImageValidationError(
            f"{label.capitalize()} was uploaded as {declared}, which is not a "
            "supported image type."
        )

    sniffed = sniff_image_content_type(data)
    if sniffed is None:
        raise ImageValidationError(
            f"{label.capitalize()} is not a JPEG or PNG image. "
            "Those are the only image formats the YouCam File API documents."
        )

    # `image/jpg` is a common but non-standard spelling of `image/jpeg`, so treat
    # the pair as equivalent rather than rejecting an otherwise valid upload.
    equivalent = {declared, sniffed} <= {"image/jpg", "image/jpeg"}
    if declared and declared != sniffed and not equivalent:
        raise ImageValidationError(
            f"{label.capitalize()} was uploaded as {declared} but its contents "
            f"look like {sniffed}."
        )

    return ValidatedImage(
        data=data,
        content_type=CANONICAL_CONTENT_TYPES[sniffed],
        size_bytes=len(data),
    )


def build_file_name(label: str, content_type: str) -> str:
    """Build a safe, vendor-facing file name.

    The caller-supplied file name is intentionally not used: it is user input and
    it travels to a third-party API. `label` must be a constant chosen by us.
    """
    extension = EXTENSIONS[content_type]
    return f"looklock-{label}{extension}"
