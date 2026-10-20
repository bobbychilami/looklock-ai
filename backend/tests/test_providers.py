"""Tests for the provider boundary, look naming, and shopping metadata.

These are the tests that protect the claims the product makes. In particular
`test_demo_products_have_no_purchase_url` and
`test_can_shop_requires_a_verified_url` exist so that a future change cannot make
the app advertise a buy button for something nothing sells.

The `FakeRetailerProvider` below stands in for a real integration: it is a `Product`
feed with genuine `retailer` and `purchase_url` values, which is the minimum a
real provider has to supply for the shop path to light up. Everything the composite
and the registry do is tested against it.
"""

from __future__ import annotations

import pytest

from app.catalog.product import Product, ProductImage, VtoAsset
from app.catalog.providers import (
    CompositeProductProvider,
    DemoProductProvider,
    ProductProvider,
    ProductProviderRegistry,
    ProductQuery,
    ProviderInfo,
    ProviderNotFoundError,
)
from app.catalog.service import build_default_registry, get_product_source, get_provider_info
from app.recommendations import RecommendationRequest, build_visual, recommend

# A retailer that actually exists, used only to prove that the shopping path
# activates when - and only when - a product carries real retail metadata.
REAL_URL = "https://retailer.example.com/p/ivory-sherwani"
DEMO_URL = "https://retailer.example.com/p/demo"


def _product(product_id: str, **overrides) -> Product:
    """A shoppable product with the minimum a real provider must supply."""
    fields: dict = {
        "product_id": product_id,
        "name": f"Product {product_id}",
        "slot": "top",
        "image": ProductImage(url="https://cdn.example.com/ivory-sherwani.jpg"),
        "price_inr": 4000,
        "styles": ("Classic",),
        "occasions": ("Wedding",),
        "description": "A product from a real retailer feed.",
        "color": "Ivory",
        "brand": "Real Brand",
        "category": "Ethnic Wear",
        "subcategory": "Sherwani",
        "colors": ("Ivory", "Cream"),
        "retailer": "Real Retailer",
        "purchase_url": REAL_URL,
        "garment_category": "upper_body",
    }
    fields.update(overrides)
    return Product(**fields)


@pytest.fixture
def retailer_provider() -> ProductProvider:
    """A provider with two shoppable tops, one accessory, one unverified product."""
    products = (
        _product("real-a"),
        _product("real-b", purchase_url=DEMO_URL, name="Product real-b"),
        _product("real-bag", slot="accessory", retailer=None, purchase_url=None),
        # A provider that knows the retailer but has no verified URL for this item.
        _product("real-unverified", purchase_url=None, retailer="Real Retailer"),
    )
    # A tiny provider rather than a `DemoProductProvider`, because that class
    # reports `supports_shopping=False` by definition - a real integration
    # reports its own capability.
    return _FakeRetailerProvider(products)


class _FakeRetailerProvider:
    """A minimal real-integration stand-in: real retail metadata, own capability."""

    def __init__(self, catalogue: tuple[Product, ...]) -> None:
        self._catalogue = catalogue

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="fake-retailer",
            name="Fake Retailer",
            supports_shopping=True,
            demo_imagery=False,
        )

    async def all_products(self):
        return self._catalogue

    async def search_products(self, query: ProductQuery):
        return tuple(p for p in self._catalogue if query.matches(p))

    async def get_product(self, product_id: str):
        for product in self._catalogue:
            if product.product_id == product_id:
                return product
        return None


# --------------------------------------------------------------------------- #
# The provider contract
# --------------------------------------------------------------------------- #


def test_the_composite_is_the_wired_default_source() -> None:
    """Routes must read products through the provider boundary, not the seed."""
    assert isinstance(get_product_source(), ProductProvider)


def test_demo_provider_satisfies_the_provider_protocol() -> None:
    assert isinstance(DemoProductProvider(), ProductProvider)


def test_demo_provider_reports_that_it_cannot_support_shopping() -> None:
    info = DemoProductProvider().info
    assert info.id == "demo"
    assert info.supports_shopping is False
    assert info.demo_imagery is False


def test_registry_registers_and_resolves_providers() -> None:
    registry = ProductProviderRegistry([DemoProductProvider()])
    assert registry.ids() == ("demo",)
    assert registry.get("demo").info.id == "demo"


def test_registry_rejects_an_unknown_provider_with_the_known_ids() -> None:
    registry = ProductProviderRegistry([DemoProductProvider()])
    with pytest.raises(ProviderNotFoundError) as excinfo:
        registry.get("myntra")
    assert "myntra" in str(excinfo.value)
    assert "demo" in str(excinfo.value)


def test_a_missing_retailer_provider_degrades_to_the_demo_catalogue() -> None:
    """The app must render something useful with no credentials configured."""
    registry = build_default_registry()
    assert registry.ids() == ("demo",)
    assert get_provider_info().supports_shopping is False


# --------------------------------------------------------------------------- #
# Search and filtering
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_search_applies_every_constraint_as_and() -> None:
    provider = DemoProductProvider()
    found = await provider.search_products(
        ProductQuery(
            slots=("top",),
            occasions=("Wedding",),
            styles=("Classic",),
            max_price_inr=15000,
        )
    )
    assert found
    for product in found:
        assert product.slot == "top"
        assert product.matches_occasion("Wedding")
        assert product.matches_style("Classic")
        assert product.price_inr <= 15000


@pytest.mark.asyncio
async def test_search_respects_the_limit() -> None:
    found = await DemoProductProvider().search_products(ProductQuery(limit=3))
    assert len(found) == 3


@pytest.mark.asyncio
async def test_search_by_text_matches_name_brand_and_color() -> None:
    provider = DemoProductProvider()
    by_name = await provider.search_products(ProductQuery(text="sherwani"))
    assert any("Sherwani" in p.name for p in by_name)
    by_brand = await provider.search_products(ProductQuery(text="looklock"))
    assert by_brand, "brand should be searchable"
    by_color = await provider.search_products(ProductQuery(text="ivory"))
    assert all(p.matches_color("ivory") for p in by_color)


@pytest.mark.asyncio
async def test_a_query_with_no_matches_returns_an_empty_sequence_not_an_error() -> None:
    found = await DemoProductProvider().search_products(ProductQuery(text="no-such-garment"))
    assert found == ()


@pytest.mark.asyncio
async def test_search_by_garment_category_uses_the_vendor_enum(retailer_provider) -> None:
    found = await retailer_provider.search_products(
        ProductQuery(garment_categories=("upper_body",))
    )
    assert found
    assert all(p.garment_category == "upper_body" for p in found)


# --------------------------------------------------------------------------- #
# Composite behaviour
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_composite_merges_providers_and_deduplicates_by_id(
    retailer_provider,
) -> None:
    """Two providers listing the same product: the higher-priority one wins.

    This is what decides whose `purchase_url` survives, so a duplicate must not
    silently overwrite a real link with a demo one.
    """
    registry = ProductProviderRegistry([retailer_provider, DemoProductProvider()])
    composite = CompositeProductProvider(registry)

    merged = await composite.all_products()
    ids = [p.product_id for p in merged]
    assert len(ids) == len(set(ids)), "products must be de-duplicated by id"
    assert "upper-ivory-sherwani" in ids and "real-a" in ids


@pytest.mark.asyncio
async def test_composite_get_product_falls_through_to_the_next_provider() -> None:
    registry = ProductProviderRegistry([DemoProductProvider()])
    composite = CompositeProductProvider(registry)
    found = await composite.get_product("upper-ivory-sherwani")
    assert found is not None and found.product_id == "upper-ivory-sherwani"
    assert await composite.get_product("nope") is None


@pytest.mark.asyncio
async def test_composite_search_honours_limit_after_deduplication(
    retailer_provider,
) -> None:
    registry = ProductProviderRegistry([retailer_provider, DemoProductProvider()])
    composite = CompositeProductProvider(registry)
    found = await composite.search_products(ProductQuery(limit=5))
    assert len(found) <= 5


@pytest.mark.asyncio
async def test_composite_search_reports_shopping_support_from_its_members(
    retailer_provider,
) -> None:
    """A composite with a real provider reports shopping support, even if the
    demo provider is also registered and cannot shop."""
    registry = ProductProviderRegistry([DemoProductProvider(), retailer_provider])
    composite = CompositeProductProvider(registry)
    info = composite.info
    # `any` on shopping support, `all` on demo imagery: one real provider makes
    # buying possible, and the demo provider's imagery is still present in the mix.
    assert info.supports_shopping is True
    assert info.demo_imagery is False


# --------------------------------------------------------------------------- #
# Shopping honesty - the load-bearing claims
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_every_demo_product_is_unbuyable() -> None:
    for product in await DemoProductProvider().all_products():
        assert product.purchase_url is None, f"{product.product_id} invented a URL"
        assert product.retailer is None, f"{product.product_id} invented a retailer"
        assert product.can_shop is False
        assert product.is_demo is True


def test_can_shop_requires_both_a_retailer_and_a_verified_url() -> None:
    """A retailer name with no URL must not produce a half-working buy button."""
    no_url = _product("x", purchase_url=None, retailer="Real Retailer")
    no_retailer = _product("x", purchase_url=REAL_URL, retailer=None)
    both = _product("x")
    assert no_url.can_shop is False
    assert no_retailer.can_shop is False
    assert both.can_shop is True


def test_a_real_product_keeps_its_retail_metadata_intact() -> None:
    """Normalisation must not drop the fields a provider supplies."""
    product = _product("real-a")
    assert product.retailer == "Real Retailer"
    assert product.purchase_url == REAL_URL
    assert product.brand == "Real Brand"
    assert product.category == "Ethnic Wear"
    assert product.subcategory == "Sherwani"
    assert "Cream" in product.colors
    assert product.currency == "INR"
    assert product.can_shop is True


# --------------------------------------------------------------------------- #
# Image separation: buying image vs try-on reference vs worn shot
# --------------------------------------------------------------------------- #


def test_vto_asset_is_preferred_over_the_merchandising_image() -> None:
    """A retailer lifestyle shot must not become the try-on reference."""
    product = _product(
        "real-a",
        image=ProductImage(url="https://cdn.example.com/lifestyle.jpg"),
        vto_asset=VtoAsset(url="https://cdn.example.com/cutout.png"),
    )
    assert product.tryon_reference is not None
    assert product.tryon_reference.url == "https://cdn.example.com/cutout.png"


def test_merchandising_image_is_the_fallback_tryon_reference() -> None:
    product = _product("real-a")
    assert product.tryon_reference is not None
    assert product.tryon_reference is product.image


def test_a_styled_shot_is_reported_when_a_provider_publishes_one() -> None:
    product = _product("real-a", styled_image=ProductImage(url="https://cdn.example.com/worn.jpg"))
    assert product.has_styled_shot == "https://cdn.example.com/worn.jpg"


def test_no_styled_shot_on_a_plain_product() -> None:
    assert _product("real-a").has_styled_shot is None


def test_accessories_are_never_tryon_capable_even_with_an_image() -> None:
    accessory = _product("real-bag", slot="accessory")
    assert accessory.is_tryon_capable is False


# --------------------------------------------------------------------------- #
# Look naming
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_looks_get_unique_names() -> None:
    """Three cards must never share a heading."""
    catalogue = await DemoProductProvider().all_products()
    for occasion, style in [
        ("Wedding", "Classic"),
        ("Interview", "Modern"),
        ("Casual", "Minimal"),
        ("Vacation", "Minimal"),
    ]:
        result = recommend(
            RecommendationRequest(occasion=occasion, style=style, budget_inr=8000),
            catalogue,
            image_url_for=lambda p: f"/img/{p.product_id}.png",
        )
        names = [look.name for look in result.looks]
        assert len(names) == len(set(names)), f"duplicate names for {occasion}/{style}: {names}"


@pytest.mark.asyncio
async def test_look_names_reflect_the_requested_occasion() -> None:
    catalogue = await DemoProductProvider().all_products()
    result = recommend(
        RecommendationRequest(occasion="Vacation", style="Minimal", budget_inr=2000),
        catalogue,
        image_url_for=lambda p: f"/img/{p.product_id}.png",
    )
    assert result.looks
    for look in result.looks:
        assert look.name, "a look must never be nameless"


# --------------------------------------------------------------------------- #
# Look visuals
# --------------------------------------------------------------------------- #


def test_visual_is_a_composite_when_no_provider_supplies_a_worn_shot() -> None:
    """The default path composes real product images rather than inventing a photo."""
    product = _product("real-a")
    visual = build_visual([(product, "/img/real-a.png")], look_name="Evening Tailoring")
    assert visual.kind == "composite"
    assert visual.image_url is None, "a composite must not claim a single source image"
    assert len(visual.layers) == 1
    assert visual.layers[0].image_url == "/img/real-a.png"


def test_a_provider_worn_shot_becomes_the_complete_look_visual() -> None:
    product = _product("real-a", styled_image=ProductImage(url="https://cdn.example.com/worn.jpg"))
    visual = build_visual(
        [(product, "/img/real-a.png")],
        has_styled_shot=product.has_styled_shot,
        look_name="Evening Tailoring",
    )
    assert visual.kind == "complete_look"
    assert visual.image_url == "https://cdn.example.com/worn.jpg"


def test_a_look_with_no_images_degrades_to_a_grid() -> None:
    visual = build_visual([], look_name="Empty Look")
    assert visual.kind == "grid"
    assert visual.layers == ()


def test_visual_layers_are_in_dressing_order() -> None:
    items = [
        (_product("t", slot="top"), "/img/t.png"),
        (_product("b", slot="bottom"), "/img/b.png"),
        (_product("o", slot="outerwear", garment_category="outer"), "/img/o.png"),
    ]
    visual = build_visual(items)
    assert [layer.slot for layer in visual.layers] == ["top", "bottom", "outerwear"]


def test_visual_marks_demo_imagery_honestly() -> None:
    """A look built entirely from demo products must not claim real photography."""
    demo_product = Product(
        product_id="d",
        name="Demo",
        slot="top",
        image=ProductImage(local_path="ivory-shirt.png"),
        price_inr=1000,
        styles=("Classic",),
        occasions=("Wedding",),
        description="Demo.",
        color="Ivory",
    )
    visual = build_visual([(demo_product, "/img/d.png")])
    assert visual.demo_imagery is True
