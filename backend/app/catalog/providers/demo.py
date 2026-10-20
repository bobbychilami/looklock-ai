"""`DemoProductProvider` - the bundled catalogue, as a provider.

This is the fallback that runs when no retailer integration is configured. It is a
real implementation of the `ProductProvider` contract rather than a special case
in the recommendation engine, which is the whole point: swapping it for an
affiliate feed changes the registry and nothing else.

What makes it a good stand-in for a retailer feed:

* products carry the fields a real listing has - brand, category, subcategory,
  every colourway, retailer, currency;
* filtering goes through `ProductQuery.matches`, so it behaves identically to a
  provider that pushed the criteria into a remote search call;
* `supports_shopping` is `False` and every product has `purchase_url = None`.

That last one is deliberate and load-bearing. These products are invented, so
there is no page on any storefront that sells them. A demo provider that invented
`https://myntra.com/product/xyz` would look more complete in a screenshot and be
outright lying, and the link would 404. So `can_shop` is `False` across the board
and the UI renders an explicit "Demo product" state instead of a buy button. When
a real provider is registered, its products carry real URLs and the same UI starts
producing real "Shop at <Retailer>" links with no UI change at all.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.catalog.product import Product
from app.catalog.providers.base import ProductQuery, ProviderInfo
from app.catalog.seed import CATALOGUE

DEMO_PROVIDER_ID = "demo"
DEMO_RETAILER = "LOOKLOCK Studio"

INFO = ProviderInfo(
    id=DEMO_PROVIDER_ID,
    name="LOOKLOCK demo catalogue",
    supports_shopping=False,
    demo_imagery=False,
    notes=(
        "Fictional products with illustrative prices. No retailer listing backs "
        "them, so there is nothing to buy and no external link to offer."
    ),
)


class DemoProductProvider:
    """Serves the bundled seed catalogue through the provider contract."""

    def __init__(self, catalogue: Sequence[Product] = CATALOGUE) -> None:
        self._catalogue = tuple(catalogue)

    @property
    def info(self) -> ProviderInfo:
        return INFO

    async def all_products(self) -> Sequence[Product]:
        return self._catalogue

    async def search_products(self, query: ProductQuery) -> Sequence[Product]:
        # `matches` is shared with every future provider; this provider adds no
        # retailer-specific behaviour of its own.
        found = [product for product in self._catalogue if query.matches(product)]
        if query.limit is not None:
            found = found[: query.limit]
        return tuple(found)

    async def get_product(self, product_id: str) -> Product | None:
        for product in self._catalogue:
            if product.product_id == product_id:
                return product
        return None
