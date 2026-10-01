"""Request and response shapes for the recommendation round.

Kept separate from the engine so the ranking logic stays testable without going
through HTTP, and so the wire format can evolve without touching scoring.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.product import Occasion, Product, Slot, Style

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
    total_price_inr: int
    #: The item the try-on request should use as its reference garment.
    hero_product_id: str
    items: tuple[ScoredProduct, ...]
    score: LookScore
    #: Short phrases naming the actual attributes that earned the rank.
    reasons: tuple[str, ...]

    @property
    def hero(self) -> ScoredProduct:
        for item in self.items:
            if item.product_id == self.hero_product_id:
                return item
        raise LookupError(f"Look {self.look_id!r} has no hero product")


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
