"""`SerpApiShoppingProductProvider` - live Google Shopping, as a provider.

This is the live marketplace behind LOOKLOCK when `PRODUCT_PROVIDER=shopping`. It
talks to SerpApi's `google_shopping` engine (India-first) and normalises the
`shopping_results` it returns into LOOKLOCK's own `Product` shape, exactly like
the Amazon provider does for the Creators API. Nothing above the provider
boundary knows the difference.

Three rules from `providers/base.py` shape everything here.

**No scraping.** Only the documented SerpApi JSON endpoint is called. The API key
is read from settings and never logged or echoed into a response.

**Nothing is invented.** `price_inr` comes from SerpApi's own numeric
`extracted_price` (or is parsed from its `price` string), never from a made-up
conversion. `purchase_url` is only set from a URL SerpApi actually returned, and
it records whether that URL is the merchant's own page (`direct_retailer`) or a
Google Shopping page (`google_shopping`) so the UI can label it honestly.

**Editorial tags are ours.** SerpApi knows a title and a merchant; it has no idea
this kurta suits a wedding. Occasion and style tags are derived here from the
title, the same way the Amazon provider derives them from its browse ladder, so a
new storefront brings its own judgement and inherits the ranking unchanged.

Quota discipline is load-bearing on a 100-searches-per-month free tier: every
upstream call is memoised for the configured TTL, and a process-wide guard caps
searches per calendar month. A cache hit never touches the guard, so re-rendering
the same look cannot burn the budget.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.catalog.product import (
    Occasion,
    Product,
    ProductImage,
    Slot,
    Style,
)
from app.catalog.providers.base import ProductQuery, ProviderInfo
from app.core.config import Settings, get_settings
from app.core.serpapi_guard import SerpApiSearchGuard
from app.services.youcam.schemas import GarmentCategory

logger = logging.getLogger(__name__)

SHOPPING_PROVIDER_ID = "shopping"
SERPAPI_PROVIDER_NAME = "SerpApi Google Shopping"

#: The single documented endpoint. Every request is a GET with query parameters.
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

#: Hosts that are Google's own infrastructure rather than a merchant's page. A
#: `link` on one of these is a Google Shopping page, not a retailer's product page.
_GOOGLE_HOST_FRAGMENTS = ("google.", "googleusercontent.", "gstatic.", "gvt1.")

#: `GarmentCategory` per slot, so a live listing can be handed to try-on directly.
_SLOT_TO_GARMENT: dict[Slot, GarmentCategory] = {
    "top": "upper_body",
    "outerwear": "outer",
    "bottom": "lower_body",
    "footwear": "shoes",
    "accessory": "auto",
}

#: Title fragments per slot. Google Shopping publishes no browse-node ladder, so
#: the title is the only classification signal. Ordered most-specific first: the
#: multi-word garment forms must be tried before the generic ones.
_TITLE_SLOTS: tuple[tuple[tuple[str, ...], Slot], ...] = (
    (("sherwani", "bandhgala", "nehru jacket", "kurta", "kurti", "suit",
      "shirt", "tshirt", "t-shirt", "tee", "top", "dress", "gown", "lehenga",
      "saree", "sari", "anarkali", "jumpsuit", "blouse", "tunic"), "top"),
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

#: Phrases that signal the garment suits a given occasion. Editorial judgement,
#: kept in sync with the Amazon provider's vocabulary on purpose: the engine scores
#: every provider's products against the same tags.
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
        "classic", "heritage", "vintage", "regal", "tailored", "traditional",
        "elegant", "plain", "solid", "oxford", "polo", "blazer", "trench",
        "cardigan",
    ),
    "Modern": (
        "contemporary", "slim fit", "slim-fit", "skinny", "high rise", "high-rise",
        "mid rise", "mid-rise", "cropped", "asymmetric", "wrap", "off shoulder",
        "off-shoulder", "bodycon", "minimalist",
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

#: Colour names pulled from a title for display only. `Product.colors` stays empty
#: because a search result does not publish the full colourway list.
_COLORS: tuple[str, ...] = (
    "black", "white", "ivory", "cream", "beige", "navy", "blue", "sky blue",
    "red", "maroon", "burgundy", "pink", "rose", "green", "olive", "mustard",
    "yellow", "orange", "rust", "brown", "tan", "khaki", "grey", "gray",
    "charcoal", "purple", "lilac", "lavender", "peach", "teal", "wine", "gold",
    "silver", "bronze", "multicolour", "floral", "printed",
)

#: Focused search phrases per slot. Deliberately not combined with the shopper's
#: occasion hint: appending it makes Google rank the dominant garment word first
#: ("trousers jeans wedding sherwani kurta" comes back full of kurta sets), which
#: leaves the pool with no trousers and no complete look. Coverage of every
#: required slot is the hard requirement here; occasion-specificity is the engine's
#: job once each position has candidates.
_SLOT_KEYWORDS: dict[str, str] = {
    "top": "shirt kurta sherwani",
    "bottom": "trousers churidar jeans",
    "outerwear": "jacket blazer",
    "footwear": "shoes mojari",
    "accessory": "watch bag belt",
}

_PRICE_DIGITS = re.compile(r"[0-9]+(?:\.[0-9]+)?")


class SerpApiShoppingProviderError(RuntimeError):
    """A SerpApi call failed.

    Carries `reason` separately from the message so `/status` can say *why* the
    provider is unavailable - throttled, unauthorised, out of quota, malformed -
    without leaking the response body or the key.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class SerpApiSearchLimitReachedError(SerpApiShoppingProviderError):
    """Raised when the monthly SerpApi search budget is exhausted."""


class _SearchCache:
    """A small TTL cache of normalised upstream pages, keyed by request params.

    Deliberately in-process and unbounded-by-time-only: the whole app is
    in-memory, and the point is to stop a re-render from spending a search, not to
    be a general-purpose cache.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = max(0, int(ttl_seconds))
        self._entries: dict[str, tuple[datetime, list[Mapping[str, Any]]]] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get(self, key: str) -> list[Mapping[str, Any]] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, results = entry
        if expires_at <= self._now():
            self._entries.pop(key, None)
            return None
        return list(results)

    def set(self, key: str, results: Sequence[Mapping[str, Any]]) -> None:
        self._entries[key] = (self._now() + timedelta(seconds=self._ttl), list(results))

    def clear(self) -> None:
        self._entries.clear()


# --------------------------------------------------------------------------- #
# Normalisation helpers.
# --------------------------------------------------------------------------- #


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_google_host(url: str) -> bool:
    host = _host(url)
    return any(fragment in host for fragment in _GOOGLE_HOST_FRAGMENTS)


def _classify_slot(title: str) -> Slot | None:
    """Best-effort slot from the title. `None` drops the listing.

    Forcing an unclassifiable result into "accessory" would quietly fill looks
    with junk, so an item we cannot place is left out instead.
    """
    lowered = title.lower()
    for phrases, slot in _TITLE_SLOTS:
        if any(phrase in lowered for phrase in phrases):
            return slot
    return None


def _occasions_for(title: str, requested: Sequence[Occasion]) -> tuple[Occasion, ...]:
    """Occasion tags, with the shopper's own answer ordered first."""
    lowered = title.lower()
    found = [
        occasion
        for occasion, phrases in _OCCASION_KEYWORDS.items()
        if any(phrase in lowered for phrase in phrases)
    ]
    ordered = [o for o in requested if o in found] + [o for o in found if o not in requested]
    return tuple(ordered) or ("Casual",)


def _styles_for(title: str, requested: Sequence[Style]) -> tuple[Style, ...]:
    lowered = title.lower()
    found = [
        style
        for style, phrases in _STYLE_KEYWORDS.items()
        if any(phrase in lowered for phrase in phrases)
    ]
    ordered = [s for s in requested if s in found] + [s for s in found if s not in requested]
    return tuple(ordered) or ("Classic",)


def _color_from(title: str) -> str:
    lowered = title.lower()
    for color in _COLORS:
        if color in lowered:
            return color.title()
    return "As shown"


def _thumbnail(item: Mapping[str, Any]) -> ProductImage | None:
    """The best available image URL, preferring SerpApi's own thumbnail.

    Its URL is what the browser fetches; we never mirror the pixels server-side.
    """
    for key in ("serpapi_thumbnail", "thumbnail"):
        url = item.get(key)
        if isinstance(url, str) and url.startswith("http"):
            return ProductImage(url=url, content_type="image/jpeg")
    return None


def _price_inr(item: Mapping[str, Any]) -> int | None:
    """Whole-rupee price from SerpApi's numeric field, or its price string.

    No conversion happens: the query is India-first (`gl=in`), so the reported
    price is already in INR. An item without a usable price is dropped rather than
    carried at zero, because the engine compares `price_inr` numerically and a zero
    would make a premium look appear to fit any budget.
    """
    extracted = item.get("extracted_price")
    if isinstance(extracted, int | float) and not isinstance(extracted, bool) and extracted > 0:
        return int(round(extracted))
    raw = item.get("price")
    if isinstance(raw, str):
        match = _PRICE_DIGITS.search(raw.replace(",", ""))
        if match:
            try:
                value = float(match.group())
            except ValueError:
                return None
            if value > 0:
                return int(round(value))
    return None


def _purchase_link(item: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """`(url, link_type)` for the buy affordance, or `(None, None)`.

    A merchant URL that is not Google's own is a real product page and is labelled
    `direct_retailer`; a Google Shopping URL is labelled `google_shopping` so the
    UI can say "View Product" rather than imply a checkout page we did not verify.
    """
    link = item.get("link")
    product_link = item.get("product_link")
    if isinstance(link, str) and link.startswith("http") and not _is_google_host(link):
        return link, "direct_retailer"
    if isinstance(product_link, str) and product_link.startswith("http"):
        return product_link, "google_shopping"
    if isinstance(link, str) and link.startswith("http"):
        return link, "google_shopping"
    return None, None


def _slug(title: str, url: str | None) -> str:
    digest = hashlib.sha1(f"{title}|{url or ''}".encode("utf-8")).hexdigest()
    return digest[:12]


# --------------------------------------------------------------------------- #
# The provider.
# --------------------------------------------------------------------------- #


class SerpApiShoppingProductProvider:
    """Live Google Shopping listings, normalised to `Product`.

    Implements the same `ProductProvider` contract as the demo and Amazon
    providers, so registering it changes nothing above the provider boundary. The
    API key is read from settings and never stored in a product or a log line.
    """

    id = SHOPPING_PROVIDER_ID
    name = SERPAPI_PROVIDER_NAME
    description = "Live product discovery via SerpApi Google Shopping (India-first)"

    def __init__(
        self,
        settings: Settings | None = None,
        guard: SerpApiSearchGuard | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._guard = guard or SerpApiSearchGuard(
            monthly_limit=self._settings.serpapi_monthly_search_limit
        )
        self._cache = _SearchCache(self._settings.serpapi_cache_ttl_seconds)
        self._client = client
        #: Whether `self._client` was handed to us. An injected client belongs to
        #: whoever created it, so it is never ours to close.
        self._owns_client = client is None
        #: The last upstream failure, as a shopper-safe sentence. Kept so `/status`
        #: can tell "SerpApi is down" apart from "nothing matched".
        self._last_error: str | None = None
        #: Products seen this process, so a detail lookup can be answered without a
        #: second, billable search. `google_shopping` has no GetItems-by-id call.
        self._index: dict[str, Product] = {}
        self._source_index: dict[str, Product] = {}

    # -- lifecycle ---------------------------------------------------------- #

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._settings.serpapi_timeout_seconds)
        return self._client

    async def aclose(self) -> None:
        """Release the connection pool if we created it."""
        self._cache.clear()
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # -- readiness ---------------------------------------------------------- #

    @property
    def is_configured(self) -> bool:
        """True when a key and the enable flag are present."""
        return self._settings.serpapi_is_configured

    @property
    def is_available(self) -> bool:
        """True when configured and not currently erroring out."""
        return self.is_configured and self._last_error is None

    @property
    def unavailable_reason(self) -> str:
        missing = self._settings.serpapi_missing_settings
        if missing:
            return "Not configured. Set " + ", ".join(missing) + " in the environment."
        if self._last_error:
            return self._last_error
        return ""

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name=self.name,
            supports_shopping=True,
            demo_imagery=False,
            notes=(
                "Live listings from SerpApi Google Shopping (India-first). Prices "
                "and links come from the search results; occasion and style tags are "
                "LOOKLOCK's editorial judgement derived from the listing title."
            ),
        )

    def _note_error(self, exc: SerpApiShoppingProviderError) -> None:
        self._last_error = str(exc)

    def _note_success(self) -> None:
        self._last_error = None

    # -- operations --------------------------------------------------------- #

    async def all_products(self) -> Sequence[Product]:
        """A broad apparel page, for callers that need a pool.

        `google_shopping` has no "list everything" operation, so this is a single
        generic query rather than a real inventory.
        """
        if not self.is_configured:
            return ()
        try:
            results = await self._search("clothing")
        except SerpApiShoppingProviderError as exc:
            logger.warning("SerpApi provider could not list inventory: %s", exc)
            self._note_error(exc)
            return ()
        self._note_success()
        return self._normalise_many(results, requested_occasions=(), requested_styles=())

    async def search_products(self, query: ProductQuery) -> Sequence[Product]:
        """Fan out a bounded number of slot-aware searches and normalise.

        `search_hint`/`budget_hint_inr` are treated as hints, never filters, per
        `ProductQuery`'s contract. Slot, occasion and style constraints are applied
        after normalisation because they are LOOKLOCK's editorial judgement, not
        SerpApi parameters.
        """
        if not self.is_configured:
            return ()

        merged: dict[str, Product] = {}
        failed = False
        for keywords in self._search_plans(query):
            try:
                results = await self._search(
                    keywords,
                    min_price=query.min_price_inr,
                    max_price=query.max_price_inr,
                )
            except SerpApiSearchLimitReachedError as exc:
                # Out of budget: stop asking, keep whatever we already have.
                logger.warning("SerpApi search budget exhausted: %s", exc)
                self._note_error(exc)
                failed = True
                break
            except SerpApiShoppingProviderError as exc:
                # One failed page must not discard the pages that did work.
                logger.warning("SerpApi search failed for %r: %s", keywords, exc)
                self._note_error(exc)
                failed = True
                continue
            for product in self._normalise_many(
                results,
                requested_occasions=query.occasions,
                requested_styles=query.styles,
            ):
                merged.setdefault(product.product_id, product)

        if not failed:
            self._note_success()

        self._index.update(merged)
        for product in merged.values():
            if product.source_product_id:
                self._source_index[product.source_product_id] = product

        filtered = [p for p in merged.values() if self._matches_editorial(p, query)]
        balanced = self._interleave_by_slot(filtered)
        if query.limit is not None:
            balanced = balanced[: query.limit]
        return tuple(balanced)

    async def get_product(self, product_id: str) -> Product | None:
        """Return a product already seen this process, or `None`.

        `google_shopping` offers no lookup-by-id, so a product that has not
        appeared in a search this process cannot be resolved without another
        billable query - and inventing one from the id would be dishonest. Returning
        `None` (a 404 at the route) is the accurate answer.
        """
        product = self._index.get(product_id)
        if product is not None:
            return product
        source_id = self._source_id_from_product_id(product_id)
        if source_id is not None:
            return self._source_index.get(source_id)
        return None

    # -- internals ---------------------------------------------------------- #

    @staticmethod
    def _source_id_from_product_id(product_id: str) -> str | None:
        prefix = f"{SHOPPING_PROVIDER_ID}-"
        if product_id.startswith(prefix):
            return product_id[len(prefix) :] or None
        return None

    def _search_plans(self, query: ProductQuery) -> list[str]:
        """The search phrases to issue, in priority order, bounded by config.

        One focused query per required slot guarantees every position the engine
        needs has candidates; the shopper's intent is carried by the broad pass so a
        slot query is not drowned out by it. Slot queries come first, so that if the
        budget runs out it runs out of the optional broad pass rather than of
        coverage.
        """
        plans: list[str] = []
        broad = query.search_hint or query.text
        covered = query.priority_slots or query.slots

        for slot in covered:
            words = _SLOT_KEYWORDS.get(slot)
            if words:
                plans.append(words)

        if not plans:
            plans.append(broad or self._keywords_for(query))

        budget = max(1, self._settings.serpapi_max_queries_per_request)
        plans = plans[:budget]

        if broad and len(plans) < budget and broad not in plans:
            plans.append(broad)
        return plans

    @staticmethod
    def _keywords_for(query: ProductQuery) -> str:
        if query.slots:
            words = [_SLOT_KEYWORDS.get(slot, "") for slot in query.slots]
            return " ".join(w for w in words if w) or "clothing"
        return "clothing"

    @staticmethod
    def _matches_editorial(product: Product, query: ProductQuery) -> bool:
        """Apply the constraints `google_shopping` cannot express."""
        if query.slots and product.slot not in query.slots:
            return False
        if query.occasions and not any(product.matches_occasion(o) for o in query.occasions):
            return False
        if query.styles and not any(product.matches_style(s) for s in query.styles):
            return False
        if query.colors and not any(product.matches_color(c) for c in query.colors):
            return False
        return not (query.shoppable_only and not product.can_shop)

    @staticmethod
    def _interleave_by_slot(products: Sequence[Product]) -> list[Product]:
        """Round-robin across slots so a `limit` cannot amputate a whole position."""
        buckets: dict[str, list[Product]] = {}
        for product in products:
            buckets.setdefault(product.slot, []).append(product)
        ordered: list[Product] = []
        while buckets:
            for slot in sorted(buckets):
                bucket = buckets[slot]
                if bucket:
                    ordered.append(bucket.pop(0))
                if not bucket:
                    del buckets[slot]
        return ordered

    async def _search(
        self,
        keywords: str,
        *,
        min_price: int | None = None,
        max_price: int | None = None,
    ) -> list[Mapping[str, Any]]:
        """One cached, guarded GET against SerpApi's `google_shopping` engine."""
        params: dict[str, Any] = {
            "engine": self._settings.serpapi_search_engine,
            "q": keywords,
            "gl": self._settings.serpapi_gl,
            "hl": self._settings.serpapi_hl,
            "location": self._settings.serpapi_location,
            "google_domain": "google.com",
        }
        if min_price is not None:
            params["min_price"] = int(min_price)
        if max_price is not None:
            params["max_price"] = int(max_price)

        cache_key = repr(sorted(params.items()))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        allowed, message = self._guard.can_perform_search()
        if not allowed:
            raise SerpApiSearchLimitReachedError("limit_reached", message)

        request_params = dict(params)
        request_params["api_key"] = self._settings.serpapi_api_key
        # A dropped connection in the middle of a slot fan-out used to lose that
        # slot's whole page, which can starve the look builder of, say, every bottom
        # and surface as a spurious 409. One quick retry absorbs an idle-connection
        # reset without masking a real outage (a second failure still raises).
        for attempt in range(2):
            try:
                response = await self._http().get(SERPAPI_ENDPOINT, params=request_params)
                break
            except httpx.TransportError as exc:
                if attempt:
                    raise SerpApiShoppingProviderError(
                        "network", "Could not reach SerpApi."
                    ) from exc
                await asyncio.sleep(0.4)

        if response.status_code in (401, 403):
            raise SerpApiShoppingProviderError(
                "unauthorised",
                "SerpApi rejected the API key. Check SERPAPI_API_KEY.",
            )
        if response.status_code == 429:
            raise SerpApiShoppingProviderError(
                "throttled", "SerpApi throttled the request. Retry shortly."
            )
        if response.status_code >= 400:
            raise SerpApiShoppingProviderError(
                "api_error", f"SerpApi returned HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SerpApiShoppingProviderError(
                "malformed_response", "SerpApi response was not valid JSON."
            ) from exc

        if isinstance(payload, Mapping) and payload.get("error"):
            raise SerpApiShoppingProviderError(
                "api_error", f"SerpApi reported an error: {payload['error']}"
            )

        raw_results = payload.get("shopping_results") if isinstance(payload, Mapping) else None
        results = [r for r in raw_results if isinstance(r, Mapping)] if isinstance(raw_results, list) else []

        # Only a real, billable call is recorded - after it succeeded.
        self._guard.record_search()
        self._cache.set(cache_key, results)
        return results

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
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        title = title.strip()

        slot = _classify_slot(title)
        if slot is None:
            return None

        price = _price_inr(item)
        if price is None:
            return None

        source = item.get("source")
        retailer = source.strip() if isinstance(source, str) and source.strip() else None
        purchase_url, link_type = _purchase_link(item)

        raw_id = item.get("product_id")
        source_id = str(raw_id) if raw_id is not None and str(raw_id).strip() else None
        product_id = f"{SHOPPING_PROVIDER_ID}-{source_id or _slug(title, purchase_url)}"

        return Product(
            product_id=product_id,
            name=title,
            slot=slot,
            image=_thumbnail(item) or ProductImage(),
            price_inr=price,
            styles=_styles_for(title, requested_styles),
            occasions=_occasions_for(title, requested_occasions),
            description=f"{title}. {retailer}." if retailer else f"{title}.",
            color=_color_from(title),
            category="Apparel",
            subcategory=None,
            colors=(),
            retailer=retailer,
            purchase_url=purchase_url,
            product_link_type=link_type,  # type: ignore[arg-type]
            source=SHOPPING_PROVIDER_ID,
            source_product_id=source_id,
            availability="unknown",
            garment_category=_SLOT_TO_GARMENT.get(slot),
            brand=None,
        )


__all__ = [
    "SERPAPI_PROVIDER_NAME",
    "SHOPPING_PROVIDER_ID",
    "SerpApiSearchLimitReachedError",
    "SerpApiShoppingProductProvider",
    "SerpApiShoppingProviderError",
]
