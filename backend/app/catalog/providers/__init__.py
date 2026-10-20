"""Product providers: the boundary between LOOKLOCK and wherever clothes come from.

Import from here rather than reaching into `providers.demo` or `providers.base`
directly, so the concrete set of providers can change without touching callers.
"""

from app.catalog.providers.amazon import (
    AMAZON_PROVIDER_ID,
    AmazonCreatorsClient,
    AmazonProductProvider,
    AmazonProviderError,
)
from app.catalog.providers.base import (
    CompositeProductProvider,
    ProductProvider,
    ProductProviderRegistry,
    ProductQuery,
    ProviderInfo,
    ProviderNotFoundError,
)
from app.catalog.providers.serpapi_shopping import (
    SERPAPI_PROVIDER_NAME,
    SHOPPING_PROVIDER_ID,
    SerpApiSearchLimitReachedError,
    SerpApiShoppingProductProvider,
    SerpApiShoppingProviderError,
)


__all__ = [
    "AMAZON_PROVIDER_ID",
    "AmazonCreatorsClient",
    "AmazonProductProvider",
    "AmazonProviderError",
    "CompositeProductProvider",
    "ProductProvider",
    "ProductProviderRegistry",
    "ProductQuery",
    "ProviderInfo",
    "ProviderNotFoundError",
]
