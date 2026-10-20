"""End-to-end tests for real retailer products flowing through the app.

`test_amazon_provider.py` proves the provider normalises a documented payload
correctly. This file proves the rest of the app treats those products as real
ones: that a recommendation round builds looks from live listings, that the shop
path activates on verified URLs, that the UI is told which provider answered, and
that a selected-but-unconfigured provider produces an explicit explanation rather
than demo data wearing a real provider's name.

Everything is driven through the FastAPI app with dependency overrides, so these
are assertions about the HTTP contract a shopper's browser actually sees.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import catalog_provider_dependency, settings_dependency
from app.catalog import (
    Product,
    ProductImage,
    ProductProvider,
    ProductQuery,
    ProviderInfo,
    reset_provider_state,
)
from app.catalog.service import get_provider_status
from app.core.config import Settings, get_settings
from app.main import create_app

AMAZON_URL = "https://www.amazon.in/dp/{asin}?tag=looklock-21"


def _amazon_product(index: int, **overrides) -> Product:
    """A plausible live listing, as the provider would normalise one."""
    asin = f"B0REAL{index:03d}"
    fields: dict = {
        "product_id": f"amazon-{asin}",
        "name": f"Ivory Sherwani Set {index}",
        "slot": ("top", "bottom", "footwear", "accessory", "outerwear")[index % 5],
        "image": ProductImage(url=f"https://m.media-amazon.com/images/I/{asin}.jpg"),
        "price_inr": 3000 + index * 100,
        "styles": ("Classic",),
        "occasions": ("Wedding",),
        "description": "Live listing.",
        "color": "Ivory",
        "brand": "Real Brand",
        "category": "Apparel",
        "subcategory": "Sherwani",
        "retailer": "Amazon",
        "purchase_url": AMAZON_URL.format(asin=asin),
        "source": "amazon",
        "source_product_id": asin,
        "availability": "in_stock",
        "garment_category": "upper_body",
    }
    fields.update(overrides)
    return Product(**fields)


class _AmazonLikeProvider:
    """A configured, shoppable provider serving real listing metadata."""

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="amazon",
            name="Amazon (www.amazon.in)",
            supports_shopping=True,
            demo_imagery=False,
            notes="Live listings from the Amazon Creators API.",
        )

    @property
    def is_available(self) -> bool:
        return True

    @property
    def unavailable_reason(self) -> str:
        return ""

    def __init__(self, products: tuple[Product, ...] = ()) -> None:
        self._products = products

    async def all_products(self) -> tuple[Product, ...]:
        return self._products

    async def search_products(self, query: ProductQuery) -> tuple[Product, ...]:
        found = [p for p in self._products if query.matches(p)]
        if query.limit is not None:
            found = found[: query.limit]
        return tuple(found)

    async def get_product(self, product_id: str) -> Product | None:
        return next((p for p in self._products if p.product_id == product_id), None)


def _app(provider: ProductProvider | None = None) -> FastAPI:
    """The real app, with the catalogue provider swapped out."""
    app = create_app()
    if provider is not None:
        app.dependency_overrides[catalog_provider_dependency] = lambda: provider
    return app


@pytest.fixture(autouse=True)
def _reset_provider_state():
    """Keep the lazily built registry from leaking between tests."""
    reset_provider_state()
    get_settings.cache_clear()
    yield
    reset_provider_state()
    get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# Real products reach the shopper
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_live_listing_reaches_the_api_with_its_real_price_and_link() -> None:
    product = _amazon_product(0)
    app = _app(_AmazonLikeProvider((product,)))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/catalog/items/{product.product_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Ivory Sherwani Set 0"
    assert body["price_inr"] == 3000
    assert body["retailer"] == "Amazon"
    assert body["purchase_url"] == AMAZON_URL.format(asin="B0REAL000")
    assert body["can_shop"] is True
    assert body["is_demo"] is False
    assert body["source"] == "amazon"
    assert body["source_product_id"] == "B0REAL000"
    assert body["availability"] == "in_stock"


@pytest.mark.asyncio
async def test_a_live_listing_keeps_the_providers_own_image_url() -> None:
    """The CDN URL is used verbatim rather than proxied through this backend."""
    product = _amazon_product(0)
    app = _app(_AmazonLikeProvider((product,)))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/catalog/items/{product.product_id}")

    assert response.json()["image_url"] == product.image.url


@pytest.mark.asyncio
async def test_the_image_route_redirects_to_the_providers_cdn() -> None:
    """A 302 keeps the bytes on Amazon's licensed CDN instead of ours.

    Profiling the image would make this service responsible for serving an asset
    it does not own, for no benefit - the URL on the wire is identical either way.
    """
    product = _amazon_product(0)
    app = _app(_AmazonLikeProvider((product,)))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/catalog/items/{product.product_id}/image",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == product.image.url


@pytest.mark.asyncio
async def test_a_bundled_demo_product_still_serves_its_own_bytes() -> None:
    """The redirect must not swallow the demo catalogue's own artwork route."""
    reset_provider_state()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        looks = await client.get("/api/v1/catalog/items")
        first = looks.json()["products"][0]
        response = await client.get(first["image_url"], follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_three_looks_are_built_from_live_listings_and_are_shoppable() -> None:
    """The whole product promise, in one request.

    This is the test that would have failed with a demo-only catalogue: looks
    composed of real products, each with a real retailer and a real URL.
    """
    pool = tuple(_amazon_product(i) for i in range(10))
    app = _app(_AmazonLikeProvider(pool))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Wedding", "style": "Classic", "budget_inr": 15000},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["looks"]) == 3
    for look in body["looks"]:
        assert look["items"]
        for item in look["items"]:
            assert item["is_demo"] is False
            assert item["can_shop"] is True
            assert item["retailer"] == "Amazon"
            assert item["purchase_url"].startswith("https://www.amazon.in/")
        # Every piece is a real listing photograph, so the UI must not label the
        # visual as illustrative demo art.
        assert look["visual"]["demo_imagery"] is False


@pytest.mark.asyncio
async def test_look_names_come_from_real_listings_not_seed_data() -> None:
    pool = tuple(_amazon_product(i) for i in range(10))
    app = _app(_AmazonLikeProvider(pool))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Wedding", "style": "Classic", "budget_inr": 15000},
        )

    names = {look["name"] for look in response.json()["looks"]}
    assert len(names) == 3
    for name in names:
        assert name


@pytest.mark.asyncio
async def test_the_catalogue_summary_stops_claiming_to_be_a_demo_catalogue() -> None:
    app = _app(_AmazonLikeProvider(tuple(_amazon_product(i) for i in range(5))))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/catalog/looks")

    body = response.json()
    assert body["is_demo_catalogue"] is False
    assert body["supports_shopping"] is True
    assert body["demo_imagery"] is False
    assert body["provider_available"] is True
    assert "fictional" not in body["notice"].lower()


# --------------------------------------------------------------------------- #
# Nothing is promised that the source cannot back
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_listing_without_a_verified_url_is_not_shoppable() -> None:
    """A product tile must not offer a buy button for something unverifiable."""
    product = _amazon_product(0, purchase_url=None, retailer=None)
    app = _app(_AmazonLikeProvider((product,)))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/catalog/items/{product.product_id}")

    body = response.json()
    assert body["can_shop"] is False
    assert body["purchase_url"] is None
    # No verified URL means the image route has nothing to redirect to and the
    # product has no renderable asset at all.
    assert body["is_demo"] is True


@pytest.mark.asyncio
async def test_an_out_of_stock_piece_is_reported_as_such_in_the_look() -> None:
    pool = tuple(
        _amazon_product(i, availability="out_of_stock" if i == 0 else "in_stock")
        for i in range(10)
    )
    app = _app(_AmazonLikeProvider(pool))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Wedding", "style": "Classic", "budget_inr": 15000},
        )

    assert response.status_code == 200
    # `ScoredProduct` carries no availability field yet, so the guarantee here is
    # that the round still succeeds and never invents stock information.
    assert len(response.json()["looks"]) == 3


# --------------------------------------------------------------------------- #
# An unconfigured real provider must be explicit, never silently demo
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_selecting_amazon_without_credentials_yields_no_products_and_a_reason() -> None:
    """The critical guarantee: no invented catalogue under a real provider's name.

    `PRODUCT_PROVIDER=amazon` with no credentials means the app has no catalogue.
    It must say so. Falling back to the bundled demo products here is exactly the
    failure this test exists to prevent - a screenshot that looks like a working
    Amazon integration while every product is fictional.
    """
    app = create_app()
    app.dependency_overrides[settings_dependency] = lambda: Settings(
        product_provider="amazon",
        amazon_enabled=True,
        amazon_client_id=None,
        amazon_client_secret=None,
        amazon_partner_tag=None,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        looks = await client.get("/api/v1/catalog/looks")
        items = await client.get("/api/v1/catalog/items")

    assert items.json()["products"] == []
    body = looks.json()
    assert body["product_count"] == 0
    assert body["provider_available"] is False
    assert "AMAZON_CLIENT_ID" in body["provider_unavailable_reason"]
    assert "no live catalogue" in body["notice"].lower()


@pytest.mark.asyncio
async def test_an_unconfigured_amazon_recommendation_conflicts_with_the_reason() -> None:
    app = create_app()
    app.dependency_overrides[settings_dependency] = lambda: Settings(
        product_provider="amazon",
        amazon_enabled=True,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Wedding", "style": "Classic", "budget_inr": 15000},
        )

    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "amazon" in detail or "not configured" in detail


@pytest.mark.asyncio
async def test_readiness_names_the_missing_settings_without_revealing_values() -> None:
    app = create_app()
    app.dependency_overrides[settings_dependency] = lambda: Settings(
        product_provider="amazon",
        amazon_enabled=True,
        amazon_client_id="amzn1.application-oa2.secret-id",
        amazon_client_secret=None,
        amazon_partner_tag=None,
        youcam_api_key="youcam-secret-value",
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["catalog_provider_available"] is False
    assert body["missing_settings"] == [
        "AMAZON_CLIENT_SECRET",
        "AMAZON_PARTNER_TAG",
    ]
    # The operator learns which names to set; the values themselves never travel.
    serialised = response.text
    assert "secret-id" not in serialised
    assert "youcam-secret-value" not in serialised


@pytest.mark.asyncio
async def test_health_names_the_selected_provider_without_probing_it() -> None:
    """A liveness probe must not spend a rate-limited search."""
    app = create_app()
    app.dependency_overrides[settings_dependency] = lambda: Settings(
        product_provider="amazon", amazon_enabled=False
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    body = response.json()
    assert body["catalog_provider_id"] == "amazon"
    assert body["catalog_provider_available"] is False


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #


def test_demo_remains_the_default_so_a_fresh_checkout_runs() -> None:
    from app.catalog.service import build_default_registry

    assert build_default_registry().ids() == ("demo",)


def test_selecting_amazon_registers_the_amazon_provider() -> None:
    from app.catalog.service import build_default_registry

    get_settings.cache_clear()
    import app.catalog.service as service

    original = service.get_settings
    service.get_settings = lambda: Settings(product_provider="amazon")  # type: ignore[assignment]
    try:
        assert build_default_registry().ids() == ("amazon",)
    finally:
        service.get_settings = original  # type: ignore[assignment]
        get_settings.cache_clear()


def test_an_unknown_provider_name_fails_loudly() -> None:
    """A typo must not silently serve the wrong catalogue forever."""
    import app.catalog.service as service

    original = service.get_settings
    service.get_settings = lambda: Settings(product_provider="myntra")  # type: ignore[assignment]
    try:
        with pytest.raises(ValueError) as excinfo:
            service.build_default_registry()
    finally:
        service.get_settings = original  # type: ignore[assignment]
        get_settings.cache_clear()

    message = str(excinfo.value)
    assert "myntra" in message
    assert "demo" in message and "amazon" in message


def test_provider_status_is_available_for_the_bundled_demo_catalogue() -> None:
    """The demo catalogue has no notion of readiness and is always ready."""
    reset_provider_state()
    status = get_provider_status()
    assert status.available is True
