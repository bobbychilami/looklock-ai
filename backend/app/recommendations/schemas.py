"""Request and response shapes for the recommendation round.

Kept separate from the engine so the ranking logic stays testable without going
through HTTP, and so the wire format can evolve without touching scoring.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.product import (
    Occasion,
    Product,
    ProductAvailability,
    Slot,
    Style,
)
from app.recommendations.naming import LookVisual

#: The budget buckets offered during onboarding, in INR.
#:
#: The tiers are integer rupees so the engine only ever compares numbers. The
#: open-ended top tier is represented as a generous ceiling rather than
#: `math.inf`, which keeps the request schema serialisable.
BUDGET_PRESETS_INR: tuple[int, ...] = (2000, 5000, 8000, 15000, 25000)

#: Ceiling used when a shopper picks the "₹25,000+" preset.
OPEN_BUDGET_CEILING_INR = 60000

#: Bounds for the custom budget field.
MIN_BUDGET_INR = 500
MAX_BUDGET_INR = 500000


class RecommendationRequest(BaseModel):
    """What the shopper chose during onboarding."""

    model_config = ConfigDict(extra="forbid")

    occasion: Occasion
    style: Style
    budget_inr: int = Field(
        ge=MIN_BUDGET_INR,
        le=MAX_BUDGET_INR,
        description="Total outfit budget in whole rupees.",
    )


class ScoredProduct(BaseModel):
    """One product as it appears inside a recommended look."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    name: str
    slot: Slot
    price_inr: int
    color: str
    description: str
    brand: str | None = None
    image_url: str
    is_demo: bool
    matches_occasion: bool
    matches_style: bool

    # -- shopping metadata -------------------------------------------------- #
    # Carried on every item in a look rather than fetched separately, because the
    # shopper's decision to buy is made from the look detail screen and must not
    # require a second round trip per garment.
    currency: str = "INR"
    category: str | None = None
    subcategory: str | None = None
    colors: tuple[str, ...] = ()
    retailer: str | None = None
    purchase_url: str | None = None
    #: Both a real URL and a real retailer, or neither.
    can_shop: bool = False
    #: Accessories complete a look but cannot be sent to the try-on service.
    is_tryon_capable: bool = False
    #: True when the try-on reference is a remote/CDN image the engine must fetch,
    #: which the try-on service cannot accept yet. The UI disables try-on for it.
    tryon_uses_remote_image: bool = False
    #: Which provider supplied this item, e.g. `amazon`. `None` for the bundled
    #: demo catalogue, so the UI can always tell a real listing from demo data.
    source: str | None = None
    #: The provider's own identifier for the item (an ASIN for Amazon), so a
    #: support question can be traced back to the exact listing.
    source_product_id: str | None = None
    #: Whether the source says this is buyable *right now*. A listing whose
    #: availability is unknown is reported as `unknown` rather than assumed in
    #: stock - an item can pass every style and budget rule and still be sold out.
    availability: ProductAvailability = "unknown"

    @classmethod
    def from_product(
        cls,
        product: Product,
        *,
        image_url: str,
        occasion: Occasion,
        style: Style,
    ) -> ScoredProduct:
        return cls(
            product_id=product.product_id,
            name=product.name,
            slot=product.slot,
            price_inr=product.price_inr,
            color=product.color,
            description=product.description,
            brand=product.brand,
            image_url=image_url,
            is_demo=product.is_demo,
            matches_occasion=product.matches_occasion(occasion),
            matches_style=product.matches_style(style),
            currency=product.currency,
            category=product.category,
            subcategory=product.subcategory,
            colors=product.colors,
            retailer=product.retailer,
            purchase_url=product.purchase_url,
            can_shop=product.can_shop,
            is_tryon_capable=product.is_tryon_capable,
            tryon_uses_remote_image=product.tryon_uses_remote_image,
            source=product.source,
            source_product_id=product.source_product_id,
            availability=product.availability,
        )


class LookScore(BaseModel):
    """The breakdown behind a look's ranking, so the UI can justify it."""

    model_config = ConfigDict(frozen=True)

    occasion: float = Field(ge=0.0, le=1.0)
    style: float = Field(ge=0.0, le=1.0)
    budget: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)


class LookRecommendation(BaseModel):
    """One complete outfit recommendation."""

    model_config = ConfigDict(frozen=True)

    look_id: str
    rank: int = Field(ge=1)
    #: Short editorial name derived from the look's own contents, e.g.
    #: "Ceremonial Sherwani". Never generic, never duplicated across a response.
    name: str
    total_price_inr: int
    #: The item the try-on request should use as its reference garment.
    hero_product_id: str
    items: tuple[ScoredProduct, ...]
    score: LookScore
    #: Short phrases naming the actual attributes that earned the rank.
    reasons: tuple[str, ...]
    #: How to picture this look. See `recommendations.naming` for why the options
    #: are ordered the way they are.
    visual: LookVisual

    @property
    def hero(self) -> ScoredProduct:
        for item in self.items:
            if item.product_id == self.hero_product_id:
                return item
        raise LookupError(f"Look {self.look_id!r} has no hero product")

    @property
    def shoppable_items(self) -> tuple[ScoredProduct, ...]:
        """Items that can actually be bought somewhere."""
        return tuple(item for item in self.items if item.can_shop)

    @property
    def is_shoppable(self) -> bool:
        """True when every piece has a real retailer page behind it."""
        return bool(self.items) and len(self.shoppable_items) == len(self.items)

    @property
    def retailer_names(self) -> tuple[str, ...]:
        """Distinct retailers behind this look, in item order."""
        seen: list[str] = []
        for item in self.items:
            if item.retailer and item.retailer not in seen:
                seen.append(item.retailer)
        return tuple(seen)


class RecommendationResponse(BaseModel):
    """Exactly three ranked looks, plus how they were reached.

    `notice` is the escape hatch for thin inventory: when the catalogue cannot
    fill three looks within budget, the engine relaxes its constraints in a stated
    order and says so, rather than silently returning fewer or over-budget results.
    """

    model_config = ConfigDict(frozen=True)

    occasion: Occasion
    style: Style
    budget_inr: int
    looks: tuple[LookRecommendation, ...]
    notice: str | None = None
    relaxed_constraints: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return len(self.looks) == 3
