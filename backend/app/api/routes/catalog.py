"""Catalogue browsing and deterministic outfit recommendation.

    GET  /api/v1/catalog/looks                      -> catalogue shape + vocabulary
    GET  /api/v1/catalog/items                      -> the bundled demo catalogue
    GET  /api/v1/catalog/items/{product_id}         -> one product
    GET  /api/v1/catalog/items/{product_id}/image   -> its bundled artwork
    GET  /api/v1/catalog/items/{product_id}/image.jpg -> provider artwork as JPEG
    POST /api/v1/recommendations                    -> exactly three ranked looks

Everything here is served from `app/catalog`, which is bundled demo data. There
is no database, no crawler and no retailer integration. The image endpoint exists
so the frontend never has to know where the artwork lives on disk, and so the
same URL can later be served from object storage or a CDN without a UI change.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import catalog_provider_dependency
from app.catalog import Product, ProductProvider
from app.catalog.product import Occasion, Style
from app.catalog.providers.base import ProductQuery
from app.catalog.remote_image import RemoteImageError, normalise_image
from app.catalog.repository import product_asset_path
from app.catalog.service import provider_status_for
from app.recommendations import (
    BUDGET_PRESETS_INR,
    InsufficientInventoryError,
    RecommendationRequest,
    RecommendationResponse,
    recommend,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["catalog"])

#: Display order for the answer vocabulary. These mirror the Literals the engine
#: ranks on, so the onboarding UI cannot offer an answer the API would reject.
#: `test_offers_only_vocabulary_the_schema_accepts` enforces the link.
OCCASION_ORDER: tuple[str, ...] = (
    "Wedding",
    "Date Night",
    "Interview",
    "Party",
    "Casual",
    "Vacation",
)
STYLE_ORDER: tuple[str, ...] = ("Classic", "Modern", "Bold", "Minimal")

DEMO_NOTICE = (
    "Every product here is a fictional demo item with an illustrative price. No "
    "retailer listing backs them, so there is nothing to buy and no external link "
    "to follow - the shopping panel says so rather than linking to a product page "
    "that does not exist."
)

#: How many products a recommendation round asks a provider for.
#:
#: Sized for the engine, not the network: `build_candidates` cross-products the
#: pool and then scores every combination, so tens of candidates yield tens of
#: thousands of candidates. Larger pools do not improve the three results a shopper
#: sees, they only multiply provider calls and throttle the upstream API.
CANDIDATE_POOL_SIZE = 40

#: How many products the browse endpoint returns.
#:
#: Below the provider's own per-request ceiling where the provider has one, so a
#: single upstream page satisfies it.
CATALOGUE_PAGE_SIZE = 20


def image_url_for(product: Product) -> str:
    """Absolute-path URL for a product's merchandising image.

    Relative on purpose: the Vite dev server proxies `/api`, and in production the
    same origin serves both, so no base URL is baked into stored data.

    Two sources, and the distinction matters:

    * a bundled demo product has bytes on disk, so it gets this backend's own image
      route and the frontend never learns where the artwork lives;
    * a provider listing already points at a licensed, cacheable image URL, and
      proxying it would only add latency and a bandwidth bill. Its own URL is used
      verbatim.
    """
    if product.image.url:
        return product.image.url
    return f"/api/v1/catalog/items/{product.product_id}/image"


def candidate_pool_for(request: RecommendationRequest) -> ProductQuery:
    """Turn the shopper's answers into the provider query that fills a pool.

    The engine still receives a plain list of `Product` and scores it exactly as
    before; this only decides *which* products it is given, so every ranking rule
    and every relaxation step stays untouched.

    Nothing here is a hard filter, and that is the point. Filtering the pool by
    occasion, style or price before scoring would quietly delete the fallback
    candidates the engine relaxes toward - a low-budget wedding look is built from
    pieces that do not themselves look wedding-appropriate - and turn today's
    graceful degradation into an empty result. Instead the answers travel as
    `search_hint` (Amazon's `keywords`) and `budget_hint_inr` (Amazon's price
    sort), which change *which* candidates come back without removing any.
    """
    return ProductQuery(
        search_hint=_search_hint_for(request),
        budget_hint_inr=request.budget_inr,
        # Top and bottom are required for any complete look, so a remote provider
        # is asked to guarantee coverage of those two positions. This filters
        # nothing - the optional slots stay eligible - it only tells the provider
        # which gaps in its pool would be fatal rather than merely disappointing.
        priority_slots=("top", "bottom"),
        limit=CANDIDATE_POOL_SIZE,
    )


#: Search phrases per occasion, used as `keywords` for a remote provider.
#:
#: Kept short and concrete because they go into a marketplace search box, not into
#: a semantic index: long, comma-heavy phrases are exactly what a keyword search
#: handles worst.
_OCCASION_SEARCH_TERMS: dict[str, str] = {
    "Wedding": "wedding sherwani kurta",
    "Date Night": "evening dress heels",
    "Interview": "formal shirt blazer trousers",
    "Party": "party dress sequin",
    "Casual": "casual t-shirt jeans",
    "Vacation": "vacation linen kurti",
}


def _search_hint_for(request: RecommendationRequest) -> str:
    """One phrase describing the occasion and style, for a provider's search box."""
    occasion = _OCCASION_SEARCH_TERMS.get(request.occasion, request.occasion)
    return f"{occasion} {request.style}".strip()


class CatalogueSummary(BaseModel):
    """Shape of the catalogue, plus the vocabulary the UI must offer.

    Also reports what the app can actually *do* with these products, so the UI does
    not have to infer it from a sample row: `supports_shopping` is False on the
    demo catalogue, and the shop page must render an explanation rather than a buy
    button when it is.

    `provider_status` is what lets the UI be honest about a *selected but
    unreachable* provider. `supports_shopping` describes what the provider can do;
    `provider_status` describes whether it could actually answer. A configured
    Amazon integration that has no credentials yet is not the same situation as the
    demo catalogue, and the shopper-facing copy has to tell them apart.
    """

    product_count: int
    counts_by_slot: dict[str, int]
    occasions: list[str]
    styles: list[str]
    budget_presets_inr: list[int]
    is_demo_catalogue: bool
    notice: str
    #: Which providers answered, and whether any of them can produce real buy links.
    provider_id: str
    provider_name: str
    supports_shopping: bool
    demo_imagery: bool
    #: Whether the selected provider can actually answer right now, and why not.
    provider_available: bool = True
    provider_unavailable_reason: str | None = None


class ProductResponse(BaseModel):
    """A product as the UI needs it. Deliberately excludes any vendor secret."""

    product_id: str
    name: str
    slot: str
    price_inr: int
    color: str
    description: str
    styles: list[str]
    occasions: list[str]
    brand: str | None
    image_url: str
    purchase_url: str | None
    is_demo: bool
    is_tryon_capable: bool
    #: True when the reference is a remote/CDN image the engine must fetch, so the
    #: UI keeps try-on disabled for this piece.
    tryon_uses_remote_image: bool = False

    # -- normalised retail metadata ----------------------------------------- #
    # These are what let a real provider slot in without touching this file, and
    # what lets the shop page decide per item whether there is anywhere to buy it.
    currency: str = "INR"
    category: str | None = None
    subcategory: str | None = None
    colors: list[str] = []
    retailer: str | None = None
    #: True only when a real retailer page backs this product.
    can_shop: bool = False
    #: Which provider answered, and the provider's own id for the listing. Enough
    #: to tell a shopper "on Amazon" and to trace a bad link back to its source
    #: without exposing an affiliate tag or a credential.
    source: str | None = None
    source_product_id: str | None = None
    #: `in_stock` / `out_of_stock` / `unknown`, as the source reported it.
    availability: str = "unknown"

    @classmethod
    def from_product(cls, product: Product, *, image_url: str) -> ProductResponse:
        return cls(
            product_id=product.product_id,
            name=product.name,
            slot=product.slot,
            price_inr=product.price_inr,
            color=product.color,
            description=product.description,
            styles=list(product.styles),
            occasions=list(product.occasions),
            brand=product.brand,
            image_url=image_url,
            purchase_url=product.purchase_url,
            is_demo=product.is_demo,
            is_tryon_capable=product.is_tryon_capable,
            tryon_uses_remote_image=product.tryon_uses_remote_image,
            currency=product.currency,
            category=product.category,
            subcategory=product.subcategory,
            colors=list(product.colors),
            retailer=product.retailer,
            can_shop=product.can_shop,
            source=product.source,
            source_product_id=product.source_product_id,
            availability=product.availability,
        )


class CatalogueResponse(BaseModel):
    products: list[ProductResponse]
    summary: CatalogueSummary


def _summary(products: list[Product], provider: ProductProvider) -> CatalogueSummary:
    """Describe the catalogue *and the provider that actually answered*.

    Takes the provider rather than re-resolving the registry: a route may have been
    handed a specific provider, and the notice and capability flags have to describe
    that one. Deriving them from the registry instead would let the UI label real
    listings as demo art, or the reverse.
    """
    info = provider.info
    status = provider_status_for(provider)
    if not products and status.available:
        # An empty catalogue from a healthy provider is a genuine "nothing matches",
        # not an outage, and the two need different wording.
        return CatalogueSummary(
            product_count=0,
            counts_by_slot={},
            occasions=list(OCCASION_ORDER),
            styles=list(STYLE_ORDER),
            budget_presets_inr=list(BUDGET_PRESETS_INR),
            is_demo_catalogue=False,
            notice="This provider returned no listings for the current query.",
            provider_id=info.id,
            provider_name=info.name,
            supports_shopping=info.supports_shopping,
            demo_imagery=info.demo_imagery,
            provider_available=status.available,
            provider_unavailable_reason=status.reason,
        )
    if not status.available:
        # A provider that is selected but cannot answer is the case that needs its
        # own copy. Falling back to `notes` here would describe what the provider
        # *could* do while the shopper is looking at an empty catalogue.
        notice = status.message
    elif not info.supports_shopping:
        notice = DEMO_NOTICE
    else:
        notice = info.notes
    return CatalogueSummary(
        product_count=len(products),
        counts_by_slot=dict(sorted(Counter(p.slot for p in products).items())),
        occasions=list(OCCASION_ORDER),
        styles=list(STYLE_ORDER),
        budget_presets_inr=list(BUDGET_PRESETS_INR),
        # `all()` over an empty list is vacuously true, which would report an empty
        # or unreachable catalogue as a demo one - the exact mislabelling this app
        # exists to avoid. An empty catalogue is simply not demo data.
        is_demo_catalogue=bool(products) and all(p.is_demo for p in products),
        notice=notice,
        provider_id=info.id,
        provider_name=info.name,
        supports_shopping=info.supports_shopping,
        demo_imagery=info.demo_imagery,
        provider_available=status.available,
        provider_unavailable_reason=status.reason,
    )


@router.get(
    "/catalog/looks",
    response_model=CatalogueSummary,
    summary="Catalogue shape and the answer vocabulary",
)
async def catalogue_summary(
    provider: ProductProvider = Depends(catalog_provider_dependency),
) -> CatalogueSummary:
    """Everything the onboarding screen needs to render itself.

    The occasion, style and budget lists come from the backend so the UI never
    hard-codes a value the request schema would reject.
    """
    return _summary(list(await provider.all_products()), provider)


@router.get(
    "/catalog/items",
    response_model=CatalogueResponse,
    summary="The products the configured provider serves",
)
async def list_catalogue(
    slot: Annotated[str | None, Query(description="Filter by outfit slot")] = None,
    occasion: Annotated[Occasion | None, Query()] = None,
    style: Annotated[Style | None, Query()] = None,
    max_price_inr: Annotated[int | None, Query(ge=0)] = None,
    provider: ProductProvider = Depends(catalog_provider_dependency),
) -> CatalogueResponse:
    """Browse or filter the catalogue. All filters are optional and combine.

    Filters are applied through `ProductQuery` rather than by hand, so this route
    filters exactly the way every provider does. A search-driven provider cannot
    enumerate its whole catalogue, so with one configured this returns what that
    provider offers for a broad apparel query - not a complete inventory, and the
    summary says so via `product_count`.
    """
    products = list(
        await provider.search_products(
            ProductQuery(
                slots=(slot,) if slot else (),
                occasions=(occasion,) if occasion else (),
                styles=(style,) if style else (),
                max_price_inr=max_price_inr,
                limit=CATALOGUE_PAGE_SIZE,
            )
        )
    )
    return CatalogueResponse(
        products=[ProductResponse.from_product(p, image_url=image_url_for(p)) for p in products],
        summary=_summary(products, provider),
    )


@router.get(
    "/catalog/items/{product_id}",
    response_model=ProductResponse,
    summary="One catalogue product",
)
async def get_catalog_item(
    product_id: str,
    provider: ProductProvider = Depends(catalog_provider_dependency),
) -> ProductResponse:
    product = await provider.get_product(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product with id {product_id!r} exists in this catalogue.",
        )
    return ProductResponse.from_product(product, image_url=image_url_for(product))


@router.get(
    "/catalog/items/{product_id}/image",
    summary="Product artwork",
    response_class=Response,
    responses={
        200: {
            "content": {"image/png": {}, "image/jpeg": {}},
            "description": "Bundled demo artwork, or a redirect to the provider's image.",
        }
    },
)
async def get_catalog_item_image(
    product_id: str,
    provider: ProductProvider = Depends(catalog_provider_dependency),
) -> Response:
    """Serve a product's bundled artwork.

    Rejects unknown products before touching the filesystem and resolves the
    filename from the catalogue rather than the request, so there is no
    user-controlled path segment anywhere in this handler.

    A provider listing that already carries an image URL is *redirected* to rather
    than proxied. The bytes belong to the provider and are licensed for retrieval
    and caching on their CDN; copying them through this process would add
    bandwidth and make this server responsible for serving an asset it does not own.
    The 302 also means a product's image URL is unchanged on the wire whether the
    product came from disk or from a real storefront.
    """
    product = await provider.get_product(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product with id {product_id!r} exists in this catalogue.",
        )
    if product.image.url:
        return RedirectResponse(url=product.image.url, status_code=status.HTTP_302_FOUND)
    try:
        path = product_asset_path(product)
    except FileNotFoundError as exc:
        logger.error("Catalogue asset missing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This product's artwork is missing from the build.",
        ) from exc
    return Response(content=path.read_bytes(), media_type="image/png")


@router.get(
    "/catalog/items/{product_id}/image.jpg",
    summary="Provider artwork, re-encoded for the browser",
    response_class=Response,
    responses={
        200: {
            "content": {"image/jpeg": {}, "image/png": {}},
            "description": "The provider's artwork in a format every browser can render.",
        }
    },
)
async def get_catalog_item_image_normalised(
    product_id: str,
    provider: ProductProvider = Depends(catalog_provider_dependency),
) -> Response:
    """Serve a product's artwork in a format the browser is certain to render.

    The frontend loads a provider image from its own CDN URL and only calls this
    when that load fails - in practice, when a live Google Shopping thumbnail is
    WebP and the shopper's browser will not decode it. The bytes are fetched once
    with WebP left out of `Accept`, re-encoded if the CDN ignores that, and cached
    in memory, so a healthy direct load never pays for any of this.

    A bundled demo product has no provider URL and is served straight from disk,
    exactly as `/image` does, so this route is a safe thing for the UI to reference
    for any product.
    """
    product = await provider.get_product(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product with id {product_id!r} exists in this catalogue.",
        )
    if not product.image.url:
        try:
            path = product_asset_path(product)
        except FileNotFoundError as exc:
            logger.error("Catalogue asset missing: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="This product's artwork is missing from the build.",
            ) from exc
        return Response(content=path.read_bytes(), media_type="image/png")

    try:
        data, content_type = await normalise_image(product.image.url)
    except RemoteImageError as exc:
        logger.warning("Could not normalise provider image for %s: %s", product_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="This product's image could not be prepared for display.",
        ) from exc
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Three ranked looks for the shopper's answers",
)
async def create_recommendations(
    request: RecommendationRequest,
    provider: ProductProvider = Depends(catalog_provider_dependency),
) -> RecommendationResponse:
    """Rank a candidate pool against the shopper's occasion, style and budget.

    Scoring is unchanged and deterministic: `recommend` still receives a plain list
    and applies the same occasion, style, budget and completeness rules to it, so
    the same answers over the same pool always produce the same three looks in the
    same order.

    What changed is where the pool comes from. The route now asks the configured
    provider for products matching the shopper's answers - which is what a
    search-driven storefront like Amazon needs, and which the bundled demo
    catalogue satisfies trivially from memory - instead of calling `all()` and
    hoping the whole catalogue is relevant. `build_candidates` raises when a pool
    has no top or no bottom, and that becomes a `409` with the provider's own
    reason rather than an empty response.
    """
    pool = await provider.search_products(candidate_pool_for(request))
    if not pool:
        reason = provider_status_for(provider).reason
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=reason
            or (
                "No products match this occasion, style and budget. Try a wider "
                "budget or a different style."
            ),
        )
    try:
        return recommend(request, list(pool), image_url_for=image_url_for)
    except InsufficientInventoryError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
