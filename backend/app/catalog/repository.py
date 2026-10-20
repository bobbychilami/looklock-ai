"""Filesystem access for bundled catalogue assets.

Product *lookup* moved to `app/catalog/service.py` and the providers. What is left
here is the one piece of real logic the demo catalogue needs: turning a bundled
filename into a file on disk.

Image handling matters more than it looks. AI Clothes Virtual Try-On V4.0 needs a
reference garment it can fetch, and a file inside this package is not reachable by
the vendor, so `asset_path` exposes the on-disk file for the try-on service to
upload rather than pretending a local path is a URL. A real provider would return
`url` or `file_id` and never come through here at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from app.catalog.product import Product, ProductImage, VtoAsset
from app.catalog.seed import CATALOGUE
from app.services.youcam.schemas import GarmentCategory

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

#: Either kind of product image. `require_reference` returns one or the other
#: depending on whether a provider supplied a dedicated try-on asset.
AnyImage = ProductImage | VtoAsset


@lru_cache(maxsize=1)
def _index() -> dict[str, Product]:
    return {product.product_id: product for product in CATALOGUE}


def get_catalogue() -> Sequence[Product]:
    """Return every product, in a stable order."""
    return CATALOGUE


def get_product(product_id: str) -> Product | None:
    return _index().get(product_id)


def get_by_slot(slot: str) -> Sequence[Product]:
    return tuple(product for product in CATALOGUE if product.slot == slot)


def asset_path(image: AnyImage) -> Path:
    """Resolve a bundled image to a real file on disk.

    Raises rather than returning a bad path: silently handing the try-on service
    a missing file would surface much later as an opaque vendor error.
    """
    if not image.local_path:
        raise FileNotFoundError(
            f"This image has no bundled asset; {image.url or 'no url'} "
            "would have to be used instead."
        )
    path = ASSETS_DIR / image.local_path
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing catalogue asset {path.name!r}. Run "
            "`python backend/tools/generate_catalog_assets.py`."
        )
    return path


def product_asset_path(product: Product) -> Path:
    """The file backing a product's merchandising image."""
    return asset_path(product.image)


def tryon_asset_path(product: Product) -> Path:
    """The file to upload as the try-on reference, which may differ per product.

    A provider can supply a dedicated cut-out as `vto_asset`; when it does, that is
    the file, not the merchandising image.
    """
    reference = product.tryon_reference
    if reference is None:
        raise FileNotFoundError(
            f"Product {product.product_id!r} has no image that can be sent to the "
            "try-on service."
        )
    return asset_path(reference)


class StaticProductSource:
    """`ProductSource` over the bundled seed catalogue.

    Retained for direct access to the seed data and because the existing test suite
    asserts the protocol is satisfied. New code should depend on
    `app.catalog.service.get_product_source()`, which routes through the providers.
    """

    async def get(self, product_id: str) -> Product | None:
        return get_product(product_id)

    async def all(self) -> Sequence[Product]:
        return get_catalogue()

    async def search(
        self,
        query: str,
        *,
        garment_category: GarmentCategory | None = None,
        limit: int = 20,
    ) -> Sequence[Product]:
        needle = query.strip().lower()
        matches: list[Product] = []
        for product in CATALOGUE:
            if garment_category and product.garment_category != garment_category:
                continue
            haystack = f"{product.name} {product.color}".lower()
            if needle and needle not in haystack:
                continue
            matches.append(product)
            if len(matches) >= limit:
                break
        return tuple(matches)
