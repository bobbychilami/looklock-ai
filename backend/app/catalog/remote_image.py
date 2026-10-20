"""Provider artwork, re-fetched in a format the browser is certain to render.

Live Google Shopping thumbnails are frequently WebP. Every current browser can
decode WebP, so the frontend normally loads the provider URL directly and this
module is never used. It exists for the shopper whose browser cannot: when the
`<img>` fails, the frontend asks this backend for the image instead, the bytes are
fetched once, normalised to JPEG/PNG and cached in memory, so a successful direct
load never pays for any of this.

Two ways to avoid handing back WebP, tried in order:

1. Ask the CDN for something that is not WebP. The `Accept` header deliberately
   omits `image/webp`, and Google's thumbnail host answers with JPEG when it is
   not asked for WebP. This needs no image library at all.
2. If the CDN sends WebP anyway *and* Pillow happens to be installed, decode and
   re-encode to JPEG. Pillow is deliberately not a runtime dependency (see
   `tools/generate_catalog_assets.py`), so this is opportunistic only and its
   absence is a normal outcome rather than an error.
"""

from __future__ import annotations

import io
import logging
from collections import OrderedDict

import httpx

logger = logging.getLogger(__name__)

#: A plausible browser identity, so CDNs that gate on one hand back an image
#: rather than a challenge page.
_PROVIDER_USER_AGENT = "Mozilla/5.0 (compatible; LOOKLOCK/1.0; +https://looklock.ai)"

#: Deliberately leaves out `image/webp` so a negotiating CDN returns JPEG.
_JPEG_ACCEPT = "image/jpeg,image/png,image/*;q=0.8"

_FETCH_TIMEOUT_SECONDS = 8.0

#: The same ceiling the try-on path uses; a provider thumbnail never approaches it.
_MAX_IMAGE_BYTES = 12 * 1024 * 1024

#: An in-process ceiling. This is a fallback route, so traffic through it is low,
#: and a bounded cache is enough to keep a repeated failure from re-fetching.
_CACHE_MAX_ENTRIES = 128

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_cache: OrderedDict[str, tuple[bytes, str]] = OrderedDict()


class RemoteImageError(RuntimeError):
    """The provider image could not be fetched, or could not be normalised."""


def sniff_content_type(data: bytes) -> str | None:
    """Return the raster content type implied by the leading bytes, if any.

    Broader than `app.core.image_validation.sniff_image_content_type`, which only
    recognises the JPEG and PNG the try-on vendor documents: here WebP is named
    too, because recognising it is the whole point of this module.
    """
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _decode_webp(data: bytes) -> bytes | None:
    """Best-effort WebP to JPEG, using Pillow only if it is importable."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(data)) as image:
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=85, optimize=True)
            return buffer.getvalue()
    except Exception:  # noqa: BLE001 - a decode failure is an expected outcome
        logger.warning("Pillow could not decode a WebP provider image", exc_info=True)
        return None


async def normalise_image(url: str) -> tuple[bytes, str]:
    """Fetch a provider image and return `(bytes, content_type)` fit for a browser.

    The content type is always `image/jpeg` or `image/png`. Raises
    `RemoteImageError` when the bytes cannot be obtained or cannot be normalised.
    """
    cached = _cache.get(url)
    if cached is not None:
        _cache.move_to_end(url)
        return cached

    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = await client.get(
                url,
                headers={"User-Agent": _PROVIDER_USER_AGENT, "Accept": _JPEG_ACCEPT},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RemoteImageError(str(exc)) from exc

    data = response.content
    if len(data) > _MAX_IMAGE_BYTES:
        raise RemoteImageError("provider image is too large to normalise")

    content_type = sniff_content_type(data)
    if content_type == "image/webp":
        decoded = _decode_webp(data)
        if decoded is None:
            raise RemoteImageError("provider image is WebP and no decoder is available")
        data, content_type = decoded, "image/jpeg"
    elif content_type not in {"image/jpeg", "image/png"}:
        raise RemoteImageError("provider image is not a recognised raster format")

    _remember(url, data, content_type)
    return data, content_type


def _remember(url: str, data: bytes, content_type: str) -> None:
    _cache[url] = (data, content_type)
    _cache.move_to_end(url)
    while len(_cache) > _CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)


def reset_remote_image_cache() -> None:
    """Forget every cached image. Intended for tests."""
    _cache.clear()
