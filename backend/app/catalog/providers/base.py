"""The provider boundary: where products come from.

A provider answers two questions - "what can you sell me for these criteria?" and
"what is this product?" - and answers them in LOOKLOCK's `Product` shape. That
normalisation is the contract. Nothing above this line knows whether a product was
read from a bundled seed, a retailer affiliate feed, or a PIM export, and nothing
above this line is allowed to care.

Why normalise rather than pass a retailer's payload through:

* the ranking engine needs a stable `price_inr` to compare and a stable
  `occasions` tuple to score. Retailers publish neither - `occasions` in
  particular is our editorial judgement, and no vendor field maps to it;
* the UI needs one image shape and one "can I shop this?" answer. Deciding that
  once, here, is why `Product.can_shop` is a property instead of a template
  conditional;
* swapping Amazon for Myntra then becomes a new file in this package instead of a
  refactor of the engine, the look cards and the shop page.

An implementation must satisfy three properties:

* **No scraping.** A provider may talk to a documented API or read a file that
  was given to it. It may not fetch and parse retailer HTML; that is brittle,
  usually against the terms of service, and produces listings that silently rot.
* **No invented facts.** `purchase_url` and `retailer` are set only when the
  source actually supplied them. A provider that cannot verify them leaves them
  `None` and the product becomes display-only.
* **No credentials in code.** Any authenticated provider reads its key from
  `app.core.config`, never from a literal here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.catalog.product import Occasion, Product, Slot, Style
from app.services.youcam.schemas import GarmentCategory


@dataclass(frozen=True)
class ProductQuery:
    """What a caller is shopping for.

    Fields split into two kinds, and conflating them is the mistake this
    separation exists to prevent.

    **Constraints** (`slots`, `occasions`, `styles`, `colors`, `min_price_inr`,
    `max_price_inr`, `shoppable_only`, `text`) are hard filters: a product that
    fails one is not a candidate. They compose with AND. `None` means "no
    constraint", never "must be empty" - a provider that cannot filter on a field
    must ignore it rather than return nothing.

    **Hints** (`search_hint`, `budget_hint_inr`) tell a remote provider what the
    shopper wants so it can bias *which* results it returns first. They are not
    filters and `matches` deliberately ignores them: a provider that can order by
    price gets the same products a filter would have kept, but the engine still
    decides what fits the budget. Dropping a product the engine might have relaxed
    around is how a recommendation round turns into a "no matches" error.

    `max_price_inr` is deliberately per-item. Budget is a whole-look concern and
    the engine applies it; a provider filtering per item is only helping to keep
    the candidate pool small, so it must not be the tighter of the two.
    """

    text: str | None = None
    slots: tuple[Slot, ...] = ()
    occasions: tuple[Occasion, ...] = ()
    styles: tuple[Style, ...] = ()
    colors: tuple[str, ...] = ()
    #: Vendor `garment_category` values, for callers that already know what the
    #: try-on engine needs. Distinct from `slots`: several slots can map to the
    #: same vendor category.
    garment_categories: tuple[GarmentCategory, ...] = ()
    min_price_inr: int | None = None
    max_price_inr: int | None = None
    #: Only products with a real `purchase_url`. Used by "shop" surfaces.
    shoppable_only: bool = False
    limit: int | None = None
    #: Free text describing the shopper's intent, for a provider's remote search.
    #: A hint, not a filter: see the class docstring.
    search_hint: str | None = None
    #: Whole-look budget, for a provider that can bias its ranking (by price)
    #: instead of filtering items out.
    budget_hint_inr: int | None = None
    #: Slots the returned pool must be guaranteed to contain, for a provider whose
    #: remote search returns one ranked page and cannot be asked for all slots at
    #: once. A hint about *coverage*, not a filter: unlike `slots`, it never removes
    #: anything, so a look can still be enriched with outerwear or footwear that the
    #: fan-out happened not to prioritise.
    #:
    #: This exists because "top" and "bottom" are required for any complete look,
    #: so an empty pool for those slots is a hard failure rather than a graceful
    #: degradation - but blanket-filtering to them would throw away the optional
    #: pieces that make a look look considered.
    priority_slots: tuple[Slot, ...] = ()

    def matches(self, product: Product) -> bool:
        """Evaluate this query's *constraints* against a product.

        Lives here rather than in each provider so a new provider inherits correct
        filtering for free, and so a bug in one provider's filtering cannot
        quietly change what the recommender is able to build looks from.
        """
        if self.slots and product.slot not in self.slots:
            return False
        if self.garment_categories and product.garment_category not in self.garment_categories:
            return False
        if self.occasions and not any(product.matches_occasion(o) for o in self.occasions):
            return False
        if self.styles and not any(product.matches_style(s) for s in self.styles):
            return False
        if self.colors and not any(product.matches_color(c) for c in self.colors):
            return False
        if self.min_price_inr is not None and product.price_inr < self.min_price_inr:
            return False
        if self.max_price_inr is not None and product.price_inr > self.max_price_inr:
            return False
        if self.shoppable_only and not product.can_shop:
            return False
        if self.text:
            needle = self.text.strip().lower()
            haystack = f"{product.name} {product.brand or ''} {product.color}".lower()
            if needle not in haystack:
                return False
        return True


@dataclass(frozen=True)
class ProviderInfo:
    """How a provider describes itself to the UI and to logs.

    `supports_shopping` is the one that matters to a shopper. It is `False` for
    the demo provider, and the UI uses it to decide whether to offer "Shop at
    Retailer" or to say "Demo product - nothing to buy here".
    """

    id: str
    name: str
    #: True when `purchase_url` values are real, verified product pages.
    supports_shopping: bool
    #: True when the imagery is original demo art rather than a real listing photo.
    demo_imagery: bool
    notes: str = ""


@runtime_checkable
class ProductProvider(Protocol):
    """A source of products, normalised to LOOKLOCK's own shape."""

    @property
    def info(self) -> ProviderInfo:
        """Static description of this provider."""
        ...

    async def all_products(self) -> Sequence[Product]:
        """Everything available. The engine builds its candidate pool from this."""
        ...

    async def search_products(self, query: ProductQuery) -> Sequence[Product]:
        """Products matching every constraint in `query`."""
        ...

    async def get_product(self, product_id: str) -> Product | None:
        """One product, or `None` if unknown or unavailable."""
        ...


class ProviderNotFoundError(LookupError):
    """Raised when a provider id is not registered."""


class ProductProviderRegistry:
    """The set of providers the app can ask, in priority order.

    A registry rather than a single global so adding a retailer is additive: a new
    provider is registered, and `CompositeProductProvider` starts including it
    without anything else changing.
    """

    def __init__(self, providers: Sequence[ProductProvider] = ()) -> None:
        self._providers: dict[str, ProductProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: ProductProvider) -> None:
        self._providers[provider.info.id] = provider

    def get(self, provider_id: str) -> ProductProvider:
        try:
            return self._providers[provider_id]
        except KeyError:
            known = ", ".join(sorted(self._providers)) or "none"
            raise ProviderNotFoundError(
                f"No product provider with id {provider_id!r} is registered. Known: {known}."
            ) from None

    def all(self) -> Sequence[ProductProvider]:
        return tuple(self._providers.values())

    def ids(self) -> tuple[str, ...]:
        return tuple(self._providers)


@dataclass
class CompositeProductProvider:
    """Asks several providers and merges their answers.

    This is the object the app actually depends on. With one provider registered
    it is a thin pass-through; the point is that "where do products come from"
    becomes a deployment question rather than an architectural one.

    Products are de-duplicated by id with first-registered-wins, so if two
    providers list the same product the higher-priority one owns its purchase
    URL. `source_id` on each result is what lets the UI and the logs say which
    provider answered.
    """

    registry: ProductProviderRegistry
    #: Provider ids to ask, in order. Empty means "every registered provider".
    provider_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def info(self) -> ProviderInfo:
        members = self._members()
        # Shopping support is `any`: one provider that can produce verified buy
        # links is enough for the shop surface to be worth rendering.
        #
        # Demo imagery is `all`, not `any`. The UI uses this flag to decide whether
        # to tell the shopper the imagery is illustrative, so it must describe the
        # imagery the shopper will actually see. `any` would let one real provider
        # flip the flag off and quietly imply that the demo renders beside it are
        # real photographs.
        shoppable = any(p.info.supports_shopping for p in members)
        demo = all(p.info.demo_imagery for p in members)

        if len(members) == 1:
            # A single provider is the common case, and reporting `composite` there
            # would hide which storefront is actually configured from `/status` and
            # `/ready`. Reporting it truthfully costs nothing and is what an
            # operator needs when credentials are missing.
            only = members[0].info
            return ProviderInfo(
                id=only.id,
                name=only.name,
                supports_shopping=only.supports_shopping,
                demo_imagery=only.demo_imagery,
                notes=only.notes,
            )

        names = ", ".join(p.info.name for p in members)
        return ProviderInfo(
            id="composite",
            name=names or "No providers registered",
            supports_shopping=shoppable,
            demo_imagery=demo,
            notes="Merged across registered providers, highest priority first.",
        )

    def _members(self) -> tuple[ProductProvider, ...]:
        if self.provider_ids:
            return tuple(self.registry.get(pid) for pid in self.provider_ids)
        return tuple(self.registry.all())

    @property
    def is_available(self) -> bool:
        """True when at least one member could answer a request right now.

        Propagated rather than defaulting, because the composite is what the app
        actually asks. A composite that reported `True` while its only member is an
        unconfigured provider would let `/status` and `/ready` claim a live
        catalogue over an empty one.
        """
        members = self._members()
        if not members:
            return False
        return any(getattr(m, "is_available", True) for m in members)

    @property
    def unavailable_reason(self) -> str:
        """Why no member can answer, naming the first one that cannot.

        Member order is priority order, so the reason comes from the provider the
        operator most likely meant to use.
        """
        for member in self._members():
            if not getattr(member, "is_available", True):
                return str(getattr(member, "unavailable_reason", "")) or (
                    f"Provider {member.info.id!r} is unavailable."
                )
        return ""

    async def all_products(self) -> Sequence[Product]:
        return await self._merge("all_products")

    async def search_products(self, query: ProductQuery) -> Sequence[Product]:
        return await self._merge("search_products", query)

    async def get_product(self, product_id: str) -> Product | None:
        for provider in self._members():
            product = await provider.get_product(product_id)
            if product is not None:
                return product
        return None

    async def _merge(self, method: str, *args: object) -> Sequence[Product]:
        """Fan out, then de-duplicate by id keeping the first provider's copy."""
        merged: dict[str, Product] = {}
        for provider in self._members():
            found = await getattr(provider, method)(*args)
            for product in found:
                merged.setdefault(product.product_id, product)
            if method == "search_products" and isinstance(args[0], ProductQuery):
                # An exact `limit` still has to be honoured after de-duplication,
                # and a provider that returned a short page should not end the
                # search early.
                limit = args[0].limit
                if limit is not None and len(merged) >= limit:
                    break
        ordered = list(merged.values())
        if method == "search_products" and isinstance(args[0], ProductQuery):
            limit = args[0].limit
            if limit is not None:
                ordered = ordered[:limit]
        return tuple(ordered)
