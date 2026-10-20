"""`AmazonProductProvider` - the Amazon Creators API, as a provider.

This is the first real storefront behind LOOKLOCK. It exists to make the promise
in `providers/base.py` concrete: swap the registry and a shopper gets real
listings, real prices, real photographs and real "Shop on Amazon" links, while
the engine, the look cards and the shop page change nothing.

Why the Creators API rather than scraping amazon.in
----------------------------------------------------

Scraping a storefront produces listings that rot silently, breaks the moment the
markup changes, and is usually against the terms of the site being scraped. The
Creators API (the successor to PA-API 5, which Amazon has retired) is the
documented, licensed way to do this, and it is the only route this provider will
take. Everything here is built from the published operations:

* `SearchItems` - keyword/category search. Returns at most ten items per request,
  supports `minPrice`/`maxPrice`, and takes a `partnerTag`.
* `GetItems` - detail lookup by ASIN, used to hydrate a single product without
  another search.

Auth is the documented OAuth client-credentials flow: a bearer token is minted at
the regional token endpoint, cached until shortly before it expires, and sent as
`Authorization: Bearer ...` with the target locale in the `x-marketplace` header.

Two things are load-bearing beyond "it returns JSON":

**Nothing is invented.** `purchase_url` is only set from Amazon's own
`detailPageURL`, `retailer` only to `Amazon`, price only from an `OffersV2`
listing. An item whose response omits offers, image or availability comes back as
a display-only product rather than one with a guessed price or a link to a search
page. `Product.can_shop` then keeps the buy button hidden, which is the correct
behaviour for a product we cannot verify.

**Editorial tags are ours, and labelled as such.** Amazon knows the category and
the title; it has no idea this shirt is the right answer for a wedding guest. The
occasion and style tags come from `_occasions_for` / `_styles_for` below, which is
why the normalisation lives here rather than in the engine - a new provider brings
its own judgement and inherits the scoring unchanged.

`Product.image.url` is Amazon's CDN URL for the primary image, which is a
licence-permitted retrieval-and-cache resource for affiliate traffic. We store
the URL and let the browser fetch it, rather than mirroring pixels server-side;
`styled_image` is deliberately left `None` because a marketplace search result
publishes product photography, not a photograph of an outfit, and treating a
packshot as a worn shot would misattribute other garments to this listing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import httpx

from app.catalog.product import (
    Occasion,
    Product,
    ProductAvailability,
    ProductImage,
    Slot,
    Style,
)
from app.catalog.providers.base import ProductQuery, ProviderInfo
from app.core.config import Settings, get_settings
from app.services.youcam.schemas import GarmentCategory

logger = logging.getLogger(__name__)

AMAZON_PROVIDER_ID = "amazon"
AMAZON_RETAILER = "Amazon"

#: The store name shown to a shopper, kept as a literal rather than derived from
#: the marketplace so it never leaks an internal host or a partner tag.
_DISPLAY_RETAILER = AMAZON_RETAILER

#: Resources requested for every search. Deliberately minimal: each one costs
#: response size and rate-limit budget, and anything not in this list is data we
#: would not use.
_SEARCH_RESOURCES: tuple[str, ...] = (
    "images.primary.medium",
    "images.primary.large",
    "itemInfo.title",
    "itemInfo.byLineInfo",
    "itemInfo.classifications",
    "itemInfo.productInfo",
    "offersV2.listings.price",
    "offersV2.listings.availability",
    "offersV2.listings.merchantInfo",
    "offersV2.listings.condition",
    "browseNodeInfo.browseNodes",
)

#: Resources for a detail lookup. Same reasoning as above, plus the manufacturer
#: info used to guess a brand when `byLineInfo` is empty.
_ITEM_RESOURCES: tuple[str, ...] = (
    "images.primary.medium",
    "images.primary.large",
    "itemInfo.title",
    "itemInfo.byLineInfo",
    "itemInfo.classifications",
    "itemInfo.productInfo",
    "itemInfo.manufactureInfo",
    "itemInfo.features",
    "offersV2.listings.price",
    "offersV2.listings.availability",
    "offersV2.listings.merchantInfo",
    "offersV2.listings.condition",
    "browseNodeInfo.browseNodes",
)

#: `OffersV2` availability types, mapped to our three-state model.
_AVAILABILITY_MAP: dict[str, ProductAvailability] = {
    "IN_STOCK": "in_stock",
    "OUT_OF_STOCK": "out_of_stock",
    "NOT_AVAILABLE": "out_of_stock",
    "PREORDER": "in_stock",
    "BACKORDER": "in_stock",
    "LIMITED_AVAILABILITY": "in_stock",
}

#: Conditions we are willing to recommend. Anything else is a used or refurbished
#: garment, which a shopper dressing for a wedding did not ask for.
_ACCEPTABLE_CONDITIONS = {"new"}

#: --------------------------------------------------------------------------- #
# Editorial tagging.
#
# Amazon gives a title and a browse-node path. Turning those into LOOKLOCK's
# occasion and style vocabulary is judgement, and it is judgement we make
# explicitly here rather than pretending a vendor field supplies it. Each entry is
# "phrase in the title or category -> the tags that phrase implies".
# --------------------------------------------------------------------------- #

#: Phrases that signal the garment suits a given occasion.
_OCCASION_KEYWORDS: dict[Occasion, tuple[str, ...]] = {
    "Wedding": (
        "sherwani", "kurta", "kurti", "lehenga", "saree", "sari", "salwar",
        "churidar", "bandhgala", "nehru jacket", "tuxedo", "blazer", "gown",
        "anarkali", "palazzo", "dhoti", "mojari", "jutti", "formal dress",
        "occasion dress", "bridal", "sangeet", "haldi",
    ),
    "Date Night": (
        "dress", "gown", "bodycon", "midi", "blazer", "jumpsuit", "cocktail",
        "ankle boot", "heels", "slingback", "silk", "satin",
    ),
    "Interview": (
        "blazer", "suit", "dress shirt", "formal shirt", "trousers", "slacks",
        "loafers", "oxford", "brogue", "formal", "business", "tailored",
        "checked shirt", "dress pants",
    ),
    "Party": (
        "party", "sequin", "sequinned", "embellished", "cocktail", "gown",
        "cluster earring", "statement", "glitter", "metallic", "velvet",
        "bodycon", "minidress", "midi dress",
    ),
    "Casual": (
        "t-shirt", "tshirt", "tee", "jeans", "denim", "joggers", "sweatshirt",
        "hoodie", "sweater", "casual shirt", "chino", "chinos", "shorts",
        "sneakers", "tank top", "polo", "cargo", "linen shirt", "floral",
        "graphic", "printed", "oversized",
    ),
    "Vacation": (
        "linen", "cotton", "resort", "vacation", "holiday", "beach", "maxi",
        "flowy", "floral", "printed", "shorts", "slip dress", "cover up",
        "kurti", "linen trousers", "wide leg",
    ),
}

#: Phrases that signal a style axis.
_STYLE_KEYWORDS: dict[Style, tuple[str, ...]] = {
    "Classic": (
        "classic", "heritage", "vintage", "regal", "heritage", "tailored",
        "traditional", "elegant", "plain", "solid", "oxford", "polo", "blazer",
        "trench", "cardigan",
    ),
    "Modern": (
        "contemporary", "slim fit", "slim-fit", "skinny", "high rise", "high-rise",
        "mid rise", "mid-rise", "cropped", "asymmetric", "wrap", "off shoulder",
        "off-shoulder", "bodycon", "tailored", "minimalist",
    ),
    "Bold": (
        "bold", "statement", "embellished", "sequin", "sequinned", "printed",
        "floral", "graphic", "geometric", "bright", "contrast", "metallic",
        "velvet", "glitter", "embroidered", "zari", "bandhani", "ajrakh",
        "colourful", "colorful", "fringe",
    ),
    "Minimal": (
        "minimal", "minimalist", "plain", "solid", "monochrome", "clean",
        "simple", "basic", "unstyled", "quiet",
    ),
}

#: --------------------------------------------------------------------------- #
# Slot classification.
#
# `SearchItems` gives a browse-node ladder (e.g. "Clothing > Men's Clothing >
# Shirts > Formal Shirts"), which is far more reliable than matching the title, so
# the ladder is consulted first and the title is the fallback.
# --------------------------------------------------------------------------- #

#: Ordered most-specific first: a "formal shirt" browse node contains the word
#: "shirt" and must not be classified by that alone.
_BROWSE_NODE_SLOTS: tuple[tuple[tuple[str, ...], Slot], ...] = (
    (("sherwani", "bandhgala", "nehru jacket", "kurta", "kurti", "suit"), "top"),
    (("dress", "gown", "lehenga", "saree", "sari", "anarkali", "jumpsuit"), "top"),
    (("blazer", "coat", "jacket", "cardigan", "sweater", "sweatshirt", "hoodie",
      "trench", "parka", "waistcoat", "kurta jacket"), "outerwear"),
    (("trouser", "pant", "jeans", "chino", "short", "skirt", "churidar",
      "salwar", "palazzo", "pyjama", "legging", "shorts"), "bottom"),
    (("shoe", "boot", "sandal", "sneaker", "mojari", "jutti", "loafer",
      "heel", "flip flop", "slipper", "socks"), "footwear"),
    (("watch", "bag", "belt", "tie", "scarf", "shawl", "jewellery", "jewelry",
      "earring", "necklace", "bracelet", "sunglasses", "cap", "hat", "wallet",
      "cufflink", "brooch", "pocket square", "saree pallu", "dupatta", "stole",
      "handbag", "backpack", "clutch"), "accessory"),
)

#: Title fragments used when the browse ladder is unhelpful or absent. Same
#: ordering discipline as the browse nodes above: `top` is tried first because it
#: carries the specific multi-word forms ("nehru jacket", "kurta") that would
#: otherwise be swallowed by the generic "jacket" in `outerwear`, so the generic
#: garment words are deliberately absent from this row.
_TITLE_SLOTS: tuple[tuple[tuple[str, ...], Slot], ...] = (
    (("sherwani", "bandhgala", "nehru jacket", "kurta", "kurti", "suit",
      "shirt", "tshirt", "t-shirt", "tee", "top", "dress", "gown", "lehenga",
      "saree", "sari", "anarkali", "jumpsuit"), "top"),
    (("trouser", "pants", "pant", "jeans", "chino", "chinos", "shorts", "skirt",
      "churidar", "salwar", "palazzo", "pyjama", "legging"), "bottom"),
    (("jacket", "blazer", "coat", "trench", "parka", "cardigan", "waistcoat",
      "overcoat", "windbreaker", "bomber", "hoodie"), "outerwear"),
    (("shoe", "shoes", "boot", "boots", "sandal", "sneaker", "sneakers",
      "mojari", "jutti", "loafer", "loafers", "heels", "heel", "flip flop",
      "slipper", "socks", "pumps"), "footwear"),
    (("watch", "bag", "belt", "tie", "scarf", "shawl", "jewellery", "jewelry",
      "earring", "earrings", "necklace", "bracelet", "bangle", "sunglasses",
      "cap", "hat", "wallet", "cufflink", "brooch", "pocket square", "stole",
      "clutch", "backpack", "handbag", "dupatta", "pallu"), "accessory"),
)

#: `GarmentCategory` per slot, used to pick the right YouCam category up front.
_SLOT_TO_GARMENT: dict[Slot, GarmentCategory] = {
    "top": "upper_body",
    "outerwear": "outer",
    "bottom": "lower_body",
    "footwear": "shoes",
    "accessory": "auto",
}


class AmazonProviderError(RuntimeError):
    """A Creators API call failed.

    Carries `reason` separately from the message so `/status` can report *why*
    the provider is unavailable - throttled, unauthorised, or a malformed
    response - without leaking the response body, which can contain the request
    echo.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class AmazonCreatorsClient:
    """Minimal async client for the two operations this app needs.

    Wraps the documented auth flow and keeps the token out of every call site. The
    constructor takes an explicit `httpx.AsyncClient` so tests inject a transport
    rather than monkeypatching the network; production passes a real one from
    `build_default_registry`.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        clock: Any = time.monotonic,
    ) -> None:
        self._settings = settings
        self._client = client
        self._clock = clock
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._cache: dict[str, tuple[float, Any]] = {}
        #: Whether `self._client` was handed to us. An injected client belongs to
        #: whoever created it, so it is never ours to close.
        self._owns_client = client is None

    # -- lifecycle ---------------------------------------------------------- #

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.amazon_timeout_seconds,
            )
        # Operation paths are relative to the catalogue host. An injected client
        # may or may not carry a base URL, so it is set here rather than relied on.
        if str(self._client.base_url).rstrip("/") != self._settings.amazon_catalog_url.rstrip("/"):
            self._client.base_url = self._settings.amazon_catalog_url
        return self._client

    async def aclose(self) -> None:
        """Release the connection pool and forget the cached token.

        Called on shutdown so the socket is not left open and the access token is
        not carried into the next process. An injected client belongs to whoever
        created it - a test's transport, or a shared pool - so it is not closed
        here; only a client this instance created is.
        """
        self._token = None
        self._token_expires_at = 0.0
        self._cache.clear()
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # -- auth --------------------------------------------------------------- #

    async def _access_token(self) -> str:
        """Return a valid bearer token, minting one when needed.

        Refreshed a minute before expiry so a token cannot lapse between the
        check and the request it guards.
        """
        now = self._clock()
        if self._token is not None and now < self._token_expires_at:
            return self._token

        missing = self._settings.amazon_missing_settings
        if missing:
            raise AmazonProviderError(
                "not_configured",
                "Amazon Creators API is not configured; missing "
                f"{', '.join(missing)}.",
            )

        payload = {
            "grant_type": "client_credentials",
            "client_id": self._settings.amazon_client_id,
            "client_secret": self._settings.amazon_client_secret,
            "scope": "creatorsapi::default",
        }
        try:
            # The same client as the catalogue calls, addressed to the absolute
            # token URL. One pool for the whole integration, and an injected
            # transport covers auth too - which is what lets the tests exercise the
            # real auth path without a network call.
            response = await self._http().post(
                self._settings.amazon_token_url, data=payload
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                raise AmazonProviderError(
                    "unauthorised",
                    "Amazon rejected the Creators API credentials. Check "
                    "AMAZON_CLIENT_ID / AMAZON_CLIENT_SECRET and that API access "
                    "is enabled for this Associates account.",
                ) from exc
            if status == 429:
                raise AmazonProviderError(
                    "throttled",
                    "Amazon throttled the token request. Retry shortly.",
                ) from exc
            raise AmazonProviderError(
                "token_failed",
                f"Amazon token request failed with HTTP {status}.",
            ) from exc
        except httpx.HTTPError as exc:
            raise AmazonProviderError(
                "network",
                "Could not reach the Amazon token endpoint.",
            ) from exc
        except ValueError as exc:
            raise AmazonProviderError(
                "malformed_response",
                "Amazon token response was not valid JSON.",
            ) from exc

        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise AmazonProviderError(
                "malformed_response",
                "Amazon token response contained no access_token.",
            )
        # Amazon returns 3600; subtract a safety margin.
        lifetime = body.get("expires_in")
        ttl = lifetime - 60 if isinstance(lifetime, int) and lifetime > 60 else 300
        self._token = token
        self._token_expires_at = now + max(ttl, 30)
        return token

    # -- operations --------------------------------------------------------- #

    async def _post(self, path: str, payload: Mapping[str, Any], *, cache_key: str) -> Any:
        """POST a documented operation, with a short-lived memoisation."""
        cached = self._cache.get(cache_key)
        now = self._clock()
        if cached is not None and now < cached[0]:
            return cached[1]

        token = await self._access_token()
        body = dict(payload)
        # The locale lives in a header, not the body, for these operations.
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-marketplace": self._settings.amazon_marketplace,
            "User-Agent": "LOOKLOCK-AI/0.1 (affiliate partner)",
        }
        try:
            response = await self._http().post(path, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise AmazonProviderError(
                "network", "Could not reach the Amazon Creators API."
            ) from exc

        if response.status_code == 429:
            raise AmazonProviderError(
                "throttled", "Amazon throttled the request. Retry shortly."
            )
        if response.status_code in (401, 403):
            # The token may simply have expired early; drop it so the next call
            # re-mints rather than failing the shopper.
            self._token = None
            raise AmazonProviderError(
                "unauthorised", "Amazon rejected the Creators API access token."
            )
        if response.status_code >= 400:
            raise AmazonProviderError(
                "api_error", f"Amazon Creators API returned HTTP {response.status_code}."
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise AmazonProviderError(
                "malformed_response", "Amazon response was not valid JSON."
            ) from exc

        self._cache[cache_key] = (now + self._settings.amazon_cache_ttl_seconds, data)
        return data

    async def search_items(
        self, keywords: str, *, index: str = "All", **extra: Any
    ) -> Mapping[str, Any]:
        """`SearchItems`: keyword search with the budget filter pushed down.

        `minPrice`/`maxPrice` are converted to paise, which is the unit the
        documented API expects.
        """
        payload: dict[str, Any] = {
            "keywords": keywords,
            "searchIndex": index,
            "itemCount": self._settings.amazon_search_page_size,
            "partnerTag": self._settings.amazon_partner_tag,
            "resources": list(_SEARCH_RESOURCES),
            "availability": "Available",
        }
        for key, value in extra.items():
            if value is not None:
                payload[key] = value
        cache_key = "search:" + repr(sorted(payload.items()))
        return await self._post("/catalog/v1/searchItems", payload, cache_key=cache_key)

    async def get_items(self, asins: Sequence[str]) -> Mapping[str, Any]:
        """`GetItems`: detail lookup for specific ASINs."""
        payload: dict[str, Any] = {
            "itemIds": list(asins),
            "itemIdType": "ASIN",
            "partnerTag": self._settings.amazon_partner_tag,
            "resources": list(_ITEM_RESOURCES),
            "condition": "New",
        }
        cache_key = "get:" + repr(sorted(payload.items()))
        return await self._post("/catalog/v1/getItems", payload, cache_key=cache_key)


# --------------------------------------------------------------------------- #
# Normalisation helpers.
# --------------------------------------------------------------------------- #


def _extract_items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Pull `searchResult.items` or `itemsResult.items` out of a response.

    The two operations wrap their payload differently; this is the only place that
    knows, so a new operation is one entry here.
    """
    for key in ("searchResult", "itemsResult"):
        container = payload.get(key)
        if isinstance(container, Mapping):
            items = container.get("items")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, Mapping)]
    return []


def _browse_node_path(item: Mapping[str, Any]) -> str:
    """Flatten the requested browse-node ancestry into one lowercase string."""
    info = item.get("browseNodeInfo")
    nodes = info.get("browseNodes") if isinstance(info, Mapping) else None
    if not isinstance(nodes, list):
        return ""
    parts: list[str] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        ancestor = node.get("ancestor")
        if isinstance(ancestor, list):
            for link in ancestor:
                if isinstance(link, Mapping):
                    display = link.get("displayName")
                    if isinstance(display, str):
                        parts.append(display)
        display = node.get("displayName")
        if isinstance(display, str):
            parts.append(display)
    return " ".join(parts).lower()


def _classify_slot(item: Mapping[str, Any], title: str) -> Slot | None:
    """Best-effort mapping from an Amazon listing to one of our five slots.

    The browse-node ladder is trusted first; the title is the fallback. Returns
    `None` when nothing fits, and the provider drops the item - forcing an
    unclassifiable listing into "accessory" would quietly fill looks with junk.
    """
    node_text = _browse_node_path(item)
    for phrases, slot in _BROWSE_NODE_SLOTS:
        if any(phrase in node_text for phrase in phrases):
            return slot
    lowered = title.lower()
    for phrases, slot in _TITLE_SLOTS:
        if any(phrase in lowered for phrase in phrases):
            return slot
    return None


def _occasions_for(title: str, browse: str, requested: Sequence[Occasion]) -> tuple[Occasion, ...]:
    """Occasion tags for a listing.

    A provider has to answer `matches_occasion`, which is how the engine scores a
    garment. Amazon has no such field, so this derives one from the title and the
    browse path. Requested occasions are kept at the front so the engine's
    ranking sees the shopper's own answer first when it overlaps.
    """
    haystack = f"{title} {browse}".lower()
    found = [
        occasion
        for occasion, phrases in _OCCASION_KEYWORDS.items()
        if any(phrase in haystack for phrase in phrases)
    ]
    ordered = [o for o in requested if o in found] + [o for o in found if o not in requested]
    return tuple(ordered) or ("Casual",)


def _styles_for(title: str, browse: str, requested: Sequence[Style]) -> tuple[Style, ...]:
    """Style tags, derived the same way as occasions."""
    haystack = f"{title} {browse}".lower()
    found = [
        style
        for style, phrases in _STYLE_KEYWORDS.items()
        if any(phrase in haystack for phrase in phrases)
    ]
    ordered = [s for s in requested if s in found] + [s for s in found if s not in requested]
    return tuple(ordered) or ("Classic",)


def _primary_image(item: Mapping[str, Any]) -> ProductImage | None:
    """The best available primary image, preferring large over medium.

    Amazon returns sized variants; the UI wants the largest that is still a
    CDN delivery URL, and never an invented or proxied path.
    """
    images = item.get("images")
    primary = images.get("primary") if isinstance(images, Mapping) else None
    if not isinstance(primary, Mapping):
        return None
    for size in ("large", "medium"):
        entry = primary.get(size)
        url = entry.get("url") if isinstance(entry, Mapping) else None
        if isinstance(url, str) and url.startswith("http"):
            return ProductImage(url=url, content_type="image/jpeg")
    return None


def _acceptable_listings(item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Listings a shopper is actually being recommended.

    Filters to `New` and drops every used or refurbished offering. Amazon happily
    returns a used churidar for a wedding-sherwani search, and a shopper who did
    not ask for secondhand should never be shown one - so an item whose only
    listings are used is dropped entirely rather than priced at zero.
    """
    offers = item.get("offersV2")
    listings = offers.get("listings") if isinstance(offers, Mapping) else None
    if not isinstance(listings, list):
        return []
    acceptable: list[Mapping[str, Any]] = []
    for listing in listings:
        if not isinstance(listing, Mapping):
            continue
        condition = listing.get("condition")
        value = condition.get("value") if isinstance(condition, Mapping) else None
        if isinstance(value, str) and value.lower() not in _ACCEPTABLE_CONDITIONS:
            continue
        acceptable.append(listing)
    return acceptable


def _first_price(item: Mapping[str, Any]) -> tuple[int, str] | None:
    """Return `(amount, currency)` from the first acceptable listing.

    Only real `money.amount` values are used; nothing is converted, because the
    marketplace already reports in INR and an invented exchange rate would be a
    fabricated price.
    """
    for listing in _acceptable_listings(item):
        price = listing.get("price")
        money = price.get("money") if isinstance(price, Mapping) else None
        if not isinstance(money, Mapping):
            continue
        amount = money.get("amount")
        if not isinstance(amount, int | float):
            continue
        currency = money.get("currency") if isinstance(money.get("currency"), str) else "INR"
        return int(amount), currency
    return None


def _availability(item: Mapping[str, Any]) -> ProductAvailability:
    """Map `OffersV2` availability to our three-state model."""
    seen: list[ProductAvailability] = []
    for listing in _acceptable_listings(item):
        availability = listing.get("availability")
        kind = availability.get("type") if isinstance(availability, Mapping) else None
        if isinstance(kind, str):
            seen.append(_AVAILABILITY_MAP.get(kind.upper(), "unknown"))
    if "in_stock" in seen:
        return "in_stock"
    if seen and all(state == "out_of_stock" for state in seen):
        return "out_of_stock"
    return "unknown"


def _brand(item: Mapping[str, Any]) -> str | None:
    """Brand from `byLineInfo`, falling back to the manufacturer."""
    info = item.get("itemInfo")
    if not isinstance(info, Mapping):
        return None
    by_line = info.get("byLineInfo")
    brand = by_line.get("brand") if isinstance(by_line, Mapping) else None
    display = brand.get("displayValue") if isinstance(brand, Mapping) else None
    if isinstance(display, str) and display.strip():
        return display.strip()
    manufacture = info.get("manufactureInfo")
    manufacturer = (
        manufacture.get("manufacturer", {}).get("displayValue")
        if isinstance(manufacture, Mapping)
        and isinstance(manufacture.get("manufacturer"), Mapping)
        else None
    )
    return manufacturer.strip() if isinstance(manufacturer, str) and manufacturer.strip() else None


def _title(item: Mapping[str, Any]) -> str:
    info = item.get("itemInfo")
    title = info.get("title") if isinstance(info, Mapping) else None
    display = title.get("displayValue") if isinstance(title, Mapping) else None
    return display.strip() if isinstance(display, str) and display.strip() else ""


def _purchase_url(item: Mapping[str, Any]) -> str | None:
    """Amazon's own detail page, used verbatim.

    Amazon appends the partner tag to `detailPageURL`; we take it as returned.
    We never construct a URL ourselves, because a hand-built `/dp/<asin>` link is
    a claim about a page we did not read.
    """
    url = item.get("detailPageURL")
    if isinstance(url, str) and url.startswith("https://"):
        return url
    return None


def _color_from(title: str) -> str:
    """A best-effort colour name pulled from the title.

    Amazon has no colour field we request; the title carries it ("Ivory Linen
    Shirt"). Returned as a string for display, never as a filter - `Product.colors`
    stays empty because we genuinely do not know the full colourway list.
    """
    colors = (
        "black", "white", "ivory", "cream", "beige", "navy", "blue", "sky blue",
        "red", "maroon", "burgundy", "pink", "rose", "green", "olive", "mustard",
        "yellow", "orange", "rust", "brown", "tan", "khaki", "grey", "gray",
        "charcoal", "purple", "lilac", "lavender", "peach", "teal", "wine",
        "gold", "silver", "bronze", "multicolour", "floral", "printed",
    )
    lowered = title.lower()
    for color in colors:
        if color in lowered:
            return color.title()
    return "As shown"


# --------------------------------------------------------------------------- #
# The provider.
# --------------------------------------------------------------------------- #


class AmazonProductProvider:
    """Real Amazon listings, normalised to `Product`.

    Implements the same `ProductProvider` contract as the demo provider, so
    registering it changes nothing above the provider boundary. Credentials are
    read from settings, never stored here.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = AmazonCreatorsClient(self._settings)
        #: The last upstream failure, as a shopper-safe sentence.
        #
        #: Provider calls return an empty result rather than raising, because one
        #: failed request must not take down the endpoint - but "no products" and
        #: "Amazon is unreachable" are very different things to a shopper, and
        #: collapsing them would make an outage look like an empty wardrobe. The
        #: reason is kept here so `/status`, `/ready` and the 409 detail can name
        #: the real cause, and it is cleared on the next successful call so a
        #: transient blip does not leave the app permanently degraded.
        self._last_error: str | None = None

    def _note_error(self, exc: AmazonProviderError) -> None:
        self._last_error = str(exc)

    async def aclose(self) -> None:
        """Release the underlying HTTP client. See `AmazonCreatorsClient.aclose`."""
        await self._client.aclose()

    def _note_success(self) -> None:
        self._last_error = None

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=AMAZON_PROVIDER_ID,
            name=f"Amazon ({self._settings.amazon_marketplace})",
            supports_shopping=True,
            demo_imagery=False,
            notes=(
                "Live listings from the Amazon Creators API. Prices, availability "
                "and purchase links come from Amazon; occasion and style tags are "
                "LOOKLOCK's editorial judgement derived from the listing title and "
                "category."
            ),
        )

    @property
    def is_configured(self) -> bool:
        """True when credentials exist, ignoring whether Amazon is answering.

        Deliberately separate from `is_available`: the request methods gate on
        *this*, so that a transient upstream failure makes `/status` report the
        problem without also cancelling every future retry. Gating on
        `is_available` would let one error wedge the provider permanently.
        """
        return self._settings.amazon_is_configured

    @property
    def is_available(self) -> bool:
        """True when this provider could answer a request right now.

        Requires credentials *and* no outstanding upstream failure. A configured
        provider that Amazon is currently rejecting is not available, and reporting
        otherwise would let `/ready` claim a live catalogue that renders empty.
        """
        return self.is_configured and self._last_error is None

    @property
    def unavailable_reason(self) -> str:
        """Why the provider cannot answer, in operator-facing terms."""
        missing = self._settings.amazon_missing_settings
        if missing:
            return "Not configured. Set " + ", ".join(missing) + " in the environment."
        if self._last_error:
            return self._last_error
        return ""

    async def all_products(self) -> Sequence[Product]:
        """Amazon has no "list everything" operation.

        `all_products` exists because the engine wants a candidate pool. For a
        search-driven marketplace there is no such pool, so this returns the
        current apparel best-sellers as a cheap, useful default, and the
        recommendation route uses `search_products` for real queries.
        """
        if not self.is_configured:
            return ()
        try:
            payload = await self._client.search_items("clothing", index="Apparel")
        except AmazonProviderError as exc:
            logger.warning("Amazon provider could not list inventory: %s", exc)
            self._note_error(exc)
            return ()
        self._note_success()
        return self._normalise_many(
            _extract_items(payload), requested_occasions=(), requested_styles=()
        )

    async def search_products(self, query: ProductQuery) -> Sequence[Product]:
        """Push the shopper's constraints into `SearchItems` and normalise.

        `search_hint` and `budget_hint_inr` are used as *hints*, not filters,
        matching `ProductQuery`'s contract:

        * the hint becomes Amazon's `keywords`, because a keyword search is how
          this API expresses intent;
        * the budget becomes `sortBy=Price:LowToHigh` rather than a `maxPrice`
          filter. Filtering would discard the exact products the engine's budget
          relaxation is built to fall back on, whereas sorting returns the same
          affordable candidates *first* and leaves the ceiling with the engine;
        * slot, occasion and style are applied here after normalisation, because
          they are our editorial judgement and not Amazon parameters. Text is not
          re-applied locally - Amazon already did that, and re-running it would
          reject items whose slot keyword is simply absent from the title.
        """
        if not self.is_configured:
            return ()

        extra: dict[str, Any] = {}
        if query.budget_hint_inr is not None:
            # Bias toward what fits. The engine still owns the real ceiling.
            extra["sortBy"] = "Price:LowToHigh"
        elif query.styles:
            extra["sortBy"] = "Relevance"
        if query.min_price_inr is not None:
            extra["minPrice"] = int(query.min_price_inr * 100)

        merged: dict[str, Product] = {}
        failed = False
        for keywords, index in self._search_plans(query):
            try:
                payload = await self._client.search_items(
                    keywords, index=index, **extra
                )
            except AmazonProviderError as exc:
                # One failed page must not discard the pages that did work, so the
                # error is recorded and the fan-out continues. `is_available` then
                # reports the provider as degraded while the shopper still sees the
                # partial pool, rather than an unexplained empty catalogue.
                logger.warning("Amazon SearchItems failed for %r: %s", keywords, exc)
                self._note_error(exc)
                failed = True
                continue
            for product in self._normalise_many(
                _extract_items(payload),
                requested_occasions=query.occasions,
                requested_styles=query.styles,
            ):
                # Keyed by id: the same garment can legitimately appear in two
                # searches, and a duplicate would be offered twice in one look.
                merged.setdefault(product.product_id, product)

        if not failed:
            self._note_success()

        filtered = [p for p in merged.values() if self._matches_editorial(p, query)]
        # Interleaved *before* truncation so the limit cannot amputate a slot.
        balanced = self._interleave_by_slot(filtered)
        if query.limit is not None:
            balanced = balanced[: query.limit]
        return tuple(balanced)

    async def get_product(self, product_id: str) -> Product | None:
        """Fetch one product by ASIN.

        The registry keys on `product_id`, which is provider-prefixed, so the ASIN
        is recovered from the id rather than requiring the caller to know the
        provider's namespace.
        """
        asin = self._asin_from_product_id(product_id)
        if not asin or not self.is_configured:
            return None
        try:
            payload = await self._client.get_items([asin])
        except AmazonProviderError as exc:
            logger.warning("Amazon GetItems failed for %s: %s", asin, exc)
            self._note_error(exc)
            return None
        self._note_success()
        items = _extract_items(payload)
        if not items:
            return None
        products = self._normalise_many(items, requested_occasions=(), requested_styles=())
        return products[0] if products else None

    # -- internals ---------------------------------------------------------- #

    @staticmethod
    def _asin_from_product_id(product_id: str) -> str | None:
        """Recover the ASIN from `amazon-<asin>`."""
        if product_id.startswith(f"{AMAZON_PROVIDER_ID}-"):
            asin = product_id[len(AMAZON_PROVIDER_ID) + 1 :]
            return asin or None
        return None

    #: Search phrases per slot, used to fan out one query per garment position.
    _SLOT_KEYWORDS = {
        "top": "shirt kurta",
        "bottom": "trousers jeans",
        "outerwear": "jacket blazer",
        "footwear": "shoes",
        "accessory": "accessories",
    }

    def _search_plans(self, query: ProductQuery) -> list[tuple[str, str]]:
        """The `(keywords, index)` pairs to query, in priority order.

        A single search cannot build a look. `SearchItems` returns one ranked page
        of ten, and for "wedding sherwani" that page is nearly all sherwanis and
        kurtas - so a top-only pool reaches the engine and it reports that it cannot
        assemble an outfit that exists. One query per *required slot* guarantees
        every position the engine needs has candidates, which is what makes a
        complete look reachable at all.

        `priority_slots` is consulted first because it carries no filtering
        promise; `slots` is a real constraint, so if a caller stated one, honour it.
        Either way these queries only decide *which* candidates come back - nothing
        is excluded afterwards on the strength of the plan - so using them here
        cannot quietly narrow a pool the engine was meant to relax within.

        The slot queries come first so that, if the configured query budget runs
        out, it runs out of the optional broad search rather than of coverage. A
        last broad occasion/style pass then backfills slots that came back thin.
        """
        plans: list[tuple[str, str]] = []
        broad = query.search_hint or query.text
        covered = query.priority_slots or query.slots

        for slot in covered:
            words = self._SLOT_KEYWORDS.get(slot)
            if not words:
                continue
            # Combine the garment words with the shopper's intent, so a wedding
            # request returns wedding-appropriate pieces of that slot rather than
            # the cheapest shirt in the catalogue.
            keywords = f"{words} {broad}".strip() if broad else words
            index = "Shoes" if slot == "footwear" else "Apparel"
            plans.append((keywords, index))

        if not plans:
            plans.append((broad or self._keywords_for(query), "Apparel"))

        # `query.limit` is the shopper's page size, not the number of upstream
        # calls, so the fan-out is bounded by the explicit budget instead.
        budget = max(1, self._settings.amazon_max_queries_per_request)
        plans = plans[:budget]

        if broad and len(plans) < budget:
            # Slot-specific terms can be too narrow to surface everything the
            # shopper would accept, so spend any leftover budget on the intent
            # alone and let the editorial filter below judge the results.
            fallback = (broad, "Apparel")
            if fallback not in plans:
                plans.append(fallback)
        return plans

    @staticmethod
    def _interleave_by_slot(products: Sequence[Product]) -> list[Product]:
        """Round-robin products across slots, preserving order within each slot.

        Applied before any truncation so a `limit` cannot silently drop a whole
        garment position. Without it, whichever slot Amazon happened to rank first
        would fill the pool and the engine would fail on a missing bottom.
        """
        buckets: dict[str, list[Product]] = {}
        for product in products:
            buckets.setdefault(product.slot, []).append(product)
        ordered: list[Product] = []
        while buckets:
            # `sorted` keeps the output deterministic across runs.
            for slot in sorted(buckets):
                bucket = buckets[slot]
                if bucket:
                    ordered.append(bucket.pop(0))
                if not bucket:
                    del buckets[slot]
        return ordered

    @staticmethod
    def _keywords_for(query: ProductQuery) -> str:
        """A sensible search phrase when the caller did not supply one."""
        if query.slots:
            words = [
                AmazonProductProvider._SLOT_KEYWORDS.get(s, "")
                for s in query.slots
            ]
            return " ".join(w for w in words if w) or "clothing"
        return "clothing"

    @staticmethod
    def _matches_editorial(product: Product, query: ProductQuery) -> bool:
        """Apply the editorial constraints `SearchItems` cannot express."""
        if query.slots and product.slot not in query.slots:
            return False
        if query.occasions and not any(product.matches_occasion(o) for o in query.occasions):
            return False
        if query.styles and not any(product.matches_style(s) for s in query.styles):
            return False
        if query.colors and not any(product.matches_color(c) for c in query.colors):
            return False
        return not (query.shoppable_only and not product.can_shop)

    def _normalise_many(
        self,
        items: Iterable[Mapping[str, Any]],
        *,
        requested_occasions: Sequence[Occasion],
        requested_styles: Sequence[Style],
    ) -> list[Product]:
        products: list[Product] = []
        seen: set[str] = set()
        for item in items:
            product = self._normalise_one(item, requested_occasions, requested_styles)
            if product is None or product.product_id in seen:
                continue
            seen.add(product.product_id)
            products.append(product)
        return products

    def _normalise_one(
        self,
        item: Mapping[str, Any],
        requested_occasions: Sequence[Occasion],
        requested_styles: Sequence[Style],
    ) -> Product | None:
        asin = item.get("asin")
        if not isinstance(asin, str) or not asin:
            return None
        title = _title(item)
        if not title:
            return None
        browse = _browse_node_path(item)
        slot = _classify_slot(item, title)
        if slot is None:
            return None
        image = _primary_image(item)
        price = _first_price(item)
        if price is None:
            # No acceptable price means no budget check is possible, and the engine
            # compares `price_inr` numerically. A product carried at 0 would make a
            # ₹40,000 look look like it fits a ₹500 budget, so it is left out rather
            # than guessed at - which is also why no currency conversion happens
            # anywhere in this module.
            return None
        amount, currency = price
        purchase_url = _purchase_url(item)
        brand = _brand(item)

        return Product(
            product_id=f"{AMAZON_PROVIDER_ID}-{asin}",
            name=title,
            slot=slot,
            image=image or ProductImage(),
            price_inr=amount,
            styles=_styles_for(title, browse, requested_styles),
            occasions=_occasions_for(title, browse, requested_occasions),
            description=self._description(title, brand=brand, browse=browse),
            color=_color_from(title),
            currency=currency,
            category="Apparel",
            subcategory=browse.split(" > ")[-1].strip() if browse else None,
            colors=(),
            retailer=_DISPLAY_RETAILER if purchase_url else None,
            purchase_url=purchase_url,
            source=AMAZON_PROVIDER_ID,
            source_product_id=asin,
            availability=_availability(item),
            garment_category=_SLOT_TO_GARMENT.get(slot),
            brand=brand,
        )

    @staticmethod
    def _description(title: str, *, brand: str | None, browse: str) -> str:
        """One honest sentence. Never a marketing claim we did not verify."""
        bits = []
        if brand:
            bits.append(brand)
        leaf = browse.split(" ")[-1] if browse else ""
        if leaf:
            bits.append(leaf)
        context = " · ".join(b for b in bits if b)
        return f"{title}. {context}." if context else f"{title}."


def build_amazon_provider(settings: Settings | None = None) -> AmazonProductProvider:
    """Factory used by `build_default_registry`."""
    return AmazonProductProvider(settings)
