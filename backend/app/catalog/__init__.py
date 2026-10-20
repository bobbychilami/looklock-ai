"""Product catalogue: domain model, providers, and the bundled demo data.

Three layers, and the order matters:

* `product`   - what a product *is*, retailer-agnostic.
* `providers` - where products come from. A provider normalises whatever it reads
  into `Product`, so nothing above this line knows about a specific storefront.
* `service`   - the single place the rest of the app asks for products.
"""

from app.catalog.product import (
    COMPLETENESS_WEIGHTS,
    REQUIRED_SLOTS,
    SLOTS,
    Occasion,
    Product,
    ProductAvailability,
    ProductImage,
    ProductNotFoundError,
    ProductSource,
    Slot,
    Style,
    VtoAsset,
    require_reference,
)
from app.catalog.providers import (
    AMAZON_PROVIDER_ID,
    SERPAPI_PROVIDER_NAME,
    SHOPPING_PROVIDER_ID,
    SerpApiSearchLimitReachedError,
    SerpApiShoppingProductProvider,
    SerpApiShoppingProviderError,
    AmazonCreatorsClient,
    AmazonProductProvider,
    AmazonProviderError,
    CompositeProductProvider,
    ProductProvider,
    ProductProviderRegistry,
    ProductQuery,
    ProviderInfo,
    ProviderNotFoundError,
)
from app.catalog.repository import (
    ASSETS_DIR,
    StaticProductSource,
    asset_path,
    get_by_slot,
    get_catalogue,
    get_product,
)
from app.catalog.seed import CATALOGUE
from app.catalog.service import (
    ProviderStatus,
    get_product_source,
    get_provider_info,
    get_provider_registry,
    get_provider_status,
    get_source,
    reset_provider_state,
)

__all__ = [
    "ASSETS_DIR",
    "AMAZON_PROVIDER_ID",
    "CATALOGUE",
    "COMPLETENESS_WEIGHTS",
    "REQUIRED_SLOTS",
    "SLOTS",
    "AmazonCreatorsClient",
    "AmazonProductProvider",
    "AmazonProviderError",
    "CompositeProductProvider",
    "Occasion",
    "Product",
    "ProductAvailability",
    "ProductImage",
    "ProductNotFoundError",
    "ProductProvider",
    "ProductProviderRegistry",
    "ProductQuery",
    "ProductSource",
    "ProviderInfo",
    "ProviderNotFoundError",
    "ProviderStatus",
    "Slot",
    "StaticProductSource",
    "Style",
    "VtoAsset",
    "asset_path",
    "get_by_slot",
    "get_catalogue",
    "get_product",
    "get_product_source",
    "get_provider_info",
    "get_provider_registry",
    "get_provider_status",
    "get_source",
    "require_reference",
    "reset_provider_state",
]
