"""Catalogue browsing and deterministic outfit recommendation.

    GET  /api/v1/catalog/looks                      -> catalogue shape + vocabulary
    GET  /api/v1/catalog/items                      -> the bundled demo catalogue
    GET  /api/v1/catalog/items/{product_id}         -> one product
    GET  /api/v1/catalog/items/{product_id}/image   -> its bundled artwork
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
from pydantic import BaseModel

from app.catalog import Product, ProductSource, asset_path, get_source
from app.catalog.product import Occasion, Style
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
OCCASION_ORDER: tuple[str, ...] = ("Wedding", "Date Night", "Interview", "Party", "Casual")
STYLE_ORDER: tuple[str, ...] = ("Classic", "Modern", "Bold", "Minimal")

DEMO_NOTICE = (
    "Every product here is a fictional demo item. Prices are illustrative and no "
    "retailer listing backs them."
)


def image_url_for(product: Product) -> str:
    """Absolute-path URL for a product's artwork.

    Relative on purpose: the Vite dev server proxies `/api`, and in production the
    same origin serves both, so no base URL is baked into stored data.
    """
    return f"/api/v1/catalog/items/{product.product_id}/image"


class CatalogueSummary(BaseModel):
    """Shape of the catalogue, plus the vocabulary the UI must offer."""

    product_count: int
    counts_by_slot: dict[str, int]
    occasions: list[str]
    styles: list[str]
    budget_presets_inr: list[int]
    is_demo_catalogue: bool
    notice: str


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
        )


class CatalogueResponse(BaseModel):
    products: list[ProductResponse]
    summary: CatalogueSummary


def _summary(products: list[Product]) -> CatalogueSummary:
    return CatalogueSummary(
        product_count=len(products),
        counts_by_slot=dict(sorted(Counter(p.slot for p in products).items())),
        occasions=list(OCCASION_ORDER),
        styles=list(STYLE_ORDER),
        budget_presets_inr=list(BUDGET_PRESETS_INR),
        is_demo_catalogue=all(p.is_demo for p in products),
        notice=DEMO_NOTICE,
    )


@router.get(
    "/catalog/looks",
    response_model=CatalogueSummary,
    summary="Catalogue shape and the answer vocabulary",
)
async def catalogue_summary(source: ProductSource = Depends(get_source)) -> CatalogueSummary:
    """Everything the onboarding screen needs to render itself.

    The occasion, style and budget lists come from the backend so the UI never
    hard-codes a value the request schema would reject.
    """
    return _summary(list(await source.all()))


@router.get(
    "/catalog/items",
    response_model=CatalogueResponse,
    summary="The bundled demo catalogue",
)
async def list_catalogue(
    slot: Annotated[str | None, Query(description="Filter by outfit slot")] = None,
    occasion: Annotated[Occasion | None, Query()] = None,
    style: Annotated[Style | None, Query()] = None,
    max_price_inr: Annotated[int | None, Query(ge=0)] = None,
    source: ProductSource = Depends(get_source),
) -> CatalogueResponse:
    """Browse or filter the catalogue. All filters are optional and combine."""
    products = list(await source.all())
    if slot:
        products = [p for p in products if p.slot == slot]
    if occasion:
        products = [p for p in products if p.matches_occasion(occasion)]
    if style:
        products = [p for p in products if p.matches_style(style)]
    if max_price_inr is not None:
        products = [p for p in products if p.price_inr <= max_price_inr]

    return CatalogueResponse(
        products=[ProductResponse.from_product(p, image_url=image_url_for(p)) for p in products],
        summary=_summary(products),
    )


@router.get(
    "/catalog/items/{product_id}",
    response_model=ProductResponse,
    summary="One catalogue product",
)
async def get_catalog_item(
    product_id: str,
    source: ProductSource = Depends(get_source),
) -> ProductResponse:
    product = await source.get(product_id)
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
    responses={200: {"content": {"image/png": {}}, "description": "Bundled demo artwork."}},
)
async def get_catalog_item_image(
    product_id: str,
    source: ProductSource = Depends(get_source),
) -> Response:
    """Serve a product's bundled artwork.

    Rejects unknown products before touching the filesystem and resolves the
    filename from the catalogue rather than the request, so there is no
    user-controlled path segment anywhere in this handler.
    """
    product = await source.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No product with id {product_id!r} exists in this catalogue.",
        )
    try:
        path = asset_path(product)
    except FileNotFoundError as exc:
        logger.error("Catalogue asset missing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This product's artwork is missing from the build.",
        ) from exc
    return Response(content=path.read_bytes(), media_type="image/png")


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Three ranked looks for the shopper's answers",
)
async def create_recommendations(
    request: RecommendationRequest,
    source: ProductSource = Depends(get_source),
) -> RecommendationResponse:
    """Rank the catalogue against the shopper's occasion, style and budget.

    Pure and deterministic: the same catalogue and the same answers always
    produce the same three looks in the same order. When the catalogue cannot
    honour the budget, the response says so via `notice` and
    `relaxed_constraints` rather than quietly returning over-budget results.
    """
    try:
        return recommend(request, list(await source.all()), image_url_for=image_url_for)
    except InsufficientInventoryError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
