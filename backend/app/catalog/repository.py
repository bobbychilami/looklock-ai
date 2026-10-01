"""In-memory catalogue backed by the bundled demo seed data.

This is the `ProductSource` the rest of the app talks to. It is deliberately
async to match the protocol: when the seed data is replaced by a real PIM or
crawler feed, callers do not change.

Image handling is the one piece of real logic here. V4.0 needs a reference
garment it can fetch, and a file inside this package is not reachable by the
vendor, so `asset_path` exposes the on-disk file for the try-on service to upload
rather than pretending a local path is a URL.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from app.catalog.product import Product, ProductSource
from app.catalog.seed import CATALOGUE
from app.services.youcam.schemas import GarmentCategory

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


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


def asset_path(product: Product) -> Path:
    """Resolve a product's bundled image to a real file on disk.

    Raises rather than returning a bad path: silently handing the try-on service
    a missing file would surface much later as an opaque vendor error.
    """
    if not product.image.local_path:
        raise FileNotFoundError(
            f"Product {product.product_id!r} has no bundled asset; "
            f"{product.image.url or 'no url'} would have to be used instead."
        )
    path = ASSETS_DIR / product.image.local_path
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing catalogue asset {path.name!r} for product "
            f"{product.product_id!r}. Run `python backend/tools/generate_catalog_assets.py`."
        )
    return path


class StaticProductSource:
    """`ProductSource` over the bundled seed catalogue."""

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


_source = StaticProductSource()


def get_source() -> ProductSource:
    """The shared source instance. Routes and services take this."""
    return _source
