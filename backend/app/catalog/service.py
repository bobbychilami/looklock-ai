"""The catalogue service: the one place the app asks for products.

Routes and the recommendation engine depend on `get_product_source()` and nothing
else. Which providers that resolves to is a configuration decision made once, in
`build_default_registry`, and adding a retailer means adding a provider class and
one line in that function.

`get_source()` is retained as a compatibility alias because the existing routes,
the try-on service and the test suite already speak `ProductSource`. The two
protocols are deliberately compatible: `ProductSource` is the older, narrower
view (`get` / `all` / `search`) and `ProductProvider` is the one new code should
use.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.catalog.product import Product
from app.catalog.providers.amazon import AMAZON_PROVIDER_ID, AmazonProductProvider
from app.catalog.providers.base import (
    CompositeProductProvider,
    ProductProvider,
    ProductProviderRegistry,
    ProductQuery,
    ProviderInfo,
)
from app.catalog.providers.serpapi_shopping import SHOPPING_PROVIDER_ID, SerpApiShoppingProductProvider
from app.core.config import Settings, get_settings
from app.services.youcam.schemas import GarmentCategory

logger = logging.getLogger(__name__)


def build_default_registry(settings: Settings | None = None) -> ProductProviderRegistry:
    """Register the providers the app ships with, in priority order.

    **Providers are chosen explicitly.** `PRODUCT_PROVIDER` names the one provider
    to serve - there is no `auto` - so an unset value cannot quietly resolve to a
    fictional catalogue and make a misconfigured deployment look configured.

    The bundled demo catalogue is no longer selectable: every provider here is a
    real marketplace (Amazon, or Google Shopping via SerpApi). When a provider's
    credentials are absent it renders nothing but an explicit configuration message
    until they arrive, rather than falling back to invented products.

    `settings` is injected rather than read from the singleton so the provider
    choice follows the same FastAPI dependency as everything else, and stays
    overridable in tests instead of only via the process environment.

    Nothing here reads an API key. `AmazonProductProvider` reads its credentials
    from settings and reports itself unavailable when they are absent, so a missing
    credential degrades to a stated message instead of a 500.
    """
    resolved = settings or get_settings()
    selected = (resolved.product_provider or SHOPPING_PROVIDER_ID).strip().lower()

    if selected == AMAZON_PROVIDER_ID:
        providers: list[ProductProvider] = [AmazonProductProvider(resolved)]
    elif selected == SHOPPING_PROVIDER_ID:
        providers = [SerpApiShoppingProductProvider(resolved)]
    else:
        # An unknown value is a configuration mistake, not something to guess
        # about. Failing loudly here beats serving the wrong catalogue forever.
        known = f"{AMAZON_PROVIDER_ID!r}, {SHOPPING_PROVIDER_ID!r}"
        raise ValueError(
            f"PRODUCT_PROVIDER={selected!r} is not a provider this build knows. "
            f"Known providers: {known}."
        )
    return ProductProviderRegistry(providers)


class _ProviderState:
    """The composite provider, built from settings on first use.

    Built lazily rather than at import so the choice of provider follows the
    environment, and cached per `(provider, credentials present)` so a test that
    sets credentials after import gets a provider that can actually use them -
    without rebuilding the composite, and with its response cache, on every call.
    """

    def __init__(self) -> None:
        self._registry: ProductProviderRegistry | None = None
        self._composite: CompositeProductProvider | None = None
        self._key: tuple[str, bool] | None = None

    async def aclose(self) -> None:
        """Close any provider that owns a connection pool.

        Only providers that built their own HTTP client have anything to release;
        one that was handed a client belongs to whoever injected it. Anything that
        does not implement `aclose` is left alone rather than failing shutdown.
        """
        for provider in (self._registry.all() if self._registry else ()):
            close = getattr(provider, "aclose", None)
            if close is None:
                continue
            try:
                await close()
            except Exception:  # pragma: no cover - shutdown must not raise
                logger.warning(
                    "Could not close provider %s cleanly", provider.info.id, exc_info=True
                )

    def reset(self) -> None:
        """Drop the cached providers. Used by tests that change the environment."""
        self._registry = None
        self._composite = None
        self._key = None

    def get(
        self, settings: Settings | None = None
    ) -> tuple[ProductProviderRegistry, CompositeProductProvider]:
        resolved = settings or get_settings()
        # Keyed on the settings object, not on the derived values: an injected
        # Settings instance is only ever equivalent to itself, and comparing
        # instances keeps a test's overrides from being served a registry that was
        # built for a different configuration.
        if self._registry is None or self._composite is None or self._key is not resolved:
            self._registry = build_default_registry(resolved)
            self._composite = CompositeProductProvider(self._registry)
            self._key = resolved
        return self._registry, self._composite


_state = _ProviderState()


def reset_provider_state() -> None:
    """Rebuild the provider registry on next access. For tests."""
    _state.reset()


async def close_provider_state() -> None:
    """Release provider-owned connections. Called on shutdown."""
    await _state.aclose()
    _state.reset()


def get_provider_registry(settings: Settings | None = None) -> ProductProviderRegistry:
    return _state.get(settings)[0]


def get_product_source(settings: Settings | None = None) -> ProductProvider:
    """The composite provider the whole app reads products through."""
    return _state.get(settings)[1]


def get_provider_info(settings: Settings | None = None) -> ProviderInfo:
    """What the UI needs to know about where its products came from."""
    return get_product_source(settings).info


# --------------------------------------------------------------------------- #
# `ProductSource` compatibility shim.
#
# The recommendation engine and the routes were written against the older
# `ProductSource` protocol. Rather than churn every call site in a change that is
# meant to be additive, the composite is adapted to it here. New code should
# prefer `ProductProvider`.
# --------------------------------------------------------------------------- #


class _CompositeAsProductSource:
    def __init__(self, provider: ProductProvider) -> None:
        self._provider = provider

    async def get(self, product_id: str) -> Product | None:
        return await self._provider.get_product(product_id)

    async def all(self) -> Sequence[Product]:
        return await self._provider.all_products()

    async def search(
        self,
        query: str,
        *,
        garment_category: GarmentCategory | None = None,
        limit: int = 20,
    ) -> Sequence[Product]:
        return await self._provider.search_products(
            ProductQuery(
                text=query or None,
                garment_categories=(garment_category,) if garment_category else (),
                limit=limit,
            )
        )


@dataclass(frozen=True)
class ProviderStatus:
    """Whether the selected provider can answer right now, and why not.

    Separate from `ProviderInfo`, which describes what a provider *is*. A provider
    can be real, shoppable and correctly configured in principle while being
    unable to answer in practice - Amazon selected, credentials absent - and the
    shopper-facing copy has to be able to say so without either pretending the app
    has a catalogue or pretending the integration is broken.
    """

    #: `True` when the selected provider can serve products.
    available: bool
    #: Operator-facing cause. Names the missing settings, never a secret value.
    reason: str | None = None
    #: One sentence safe to show a shopper or print in a log.
    message: str = ""


def provider_status_for(provider: ProductProvider) -> ProviderStatus:
    """Report a provider's readiness.

    Reads the provider's own `is_available` / `unavailable_reason` when it exposes
    them, and treats any provider that does not as available - a provider with no
    notion of readiness (the bundled demo one) is always ready.

    Takes the provider as an argument rather than resolving it internally so a route
    that was handed a provider describes *that* provider, not whatever the registry
    would have built. Otherwise an injected provider and the summary could disagree,
    and the UI would label a real listing as demo art.
    """
    available = getattr(provider, "is_available", True)
    if available:
        return ProviderStatus(available=True, message="Catalogue provider is ready.")
    reason = (
        getattr(provider, "unavailable_reason", "")
        or "The catalogue provider is unavailable."
    )
    return ProviderStatus(
        available=False,
        reason=reason,
        message=f"No live catalogue is available. {reason}",
    )


def get_provider_status(settings: Settings | None = None) -> ProviderStatus:
    """Report the *configured* provider's readiness."""
    return provider_status_for(get_product_source(settings))


def get_source():
    """Deprecated alias for `get_product_source`, kept for existing callers.

    Resolves the composite on every call rather than capturing one, so the
    adapter always reads through the currently configured providers.
    """
    return _CompositeAsProductSource(get_product_source())


__all__ = [
    "AMAZON_PROVIDER_ID",
    "AmazonProductProvider",
    "CompositeProductProvider",
    "ProductProvider",
    "ProductProviderRegistry",
    "ProductQuery",
    "ProviderInfo",
    "ProviderStatus",
    "build_default_registry",
    "get_product_source",
    "get_provider_info",
    "get_provider_registry",
    "get_provider_status",
    "get_source",
    "provider_status_for",
    "reset_provider_state",
    "close_provider_state",
]
