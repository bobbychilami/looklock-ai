"""Product catalogue: domain model, bundled demo data, and its source."""

from app.catalog.product import (
    COMPLETENESS_WEIGHTS,
    REQUIRED_SLOTS,
    SLOTS,
    Occasion,
    Product,
    ProductImage,
    ProductNotFoundError,
    ProductSource,
    Slot,
    Style,
    require_reference,
)
from app.catalog.repository import (
    ASSETS_DIR,
    StaticProductSource,
    asset_path,
    get_by_slot,
    get_catalogue,
    get_product,
    get_source,
)
from app.catalog.seed import CATALOGUE

__all__ = [
    "ASSETS_DIR",
    "CATALOGUE",
    "COMPLETENESS_WEIGHTS",
    "REQUIRED_SLOTS",
    "SLOTS",
    "Occasion",
    "Product",
    "ProductImage",
    "ProductNotFoundError",
    "ProductSource",
    "Slot",
    "StaticProductSource",
    "Style",
    "asset_path",
    "get_by_slot",
    "get_catalogue",
    "get_product",
    "get_source",
    "require_reference",
]
