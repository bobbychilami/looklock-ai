"""Domain model for the LOOKLOCK catalogue.

Two things drive the shape of this module.

1. AI Clothes Virtual Try-On V4.0 makes a reference garment mandatory, so every
   try-on candidate must resolve to a usable garment image. `ProductImage` is
   therefore central rather than cosmetic, and `require_reference` fails loudly
   when an item cannot produce one.
2. The recommender has to *explain* its choices, so style, occasion and price are
   first-class fields on the product rather than something derived from prose.

The catalogue itself lives in `seed.py` and is served by `repository.py`. Keeping
them separate from this file means a future crawler, PIM feed or manual dropbox
can replace the static source without touching the recommendation engine, the
try-on service, or the API layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from app.services.youcam.schemas import GarmentCategory

#: Style axes offered during onboarding. Order is the order shown in the UI.
Style = Literal["Classic", "Modern", "Bold", "Minimal"]

#: Occasion axes offered during onboarding.
Occasion = Literal["Wedding", "Date Night", "Interview", "Party", "Casual"]

#: Where a garment sits in an outfit.
#:
#: `top` and `bottom` are required to build a look. `footwear` and `accessory`
#: are optional, which is what lets the engine score *completeness* as a real
#: ranking signal rather than a formality, and what allows genuinely low budgets
#: to produce a wearable result instead of an empty shelf.
Slot = Literal["top", "bottom", "footwear", "accessory"]

SLOTS: tuple[Slot, ...] = ("top", "bottom", "footwear", "accessory")

#: Slots without which a look is not an outfit.
REQUIRED_SLOTS: tuple[Slot, ...] = ("top", "bottom")

#: Slots ordered by how much they improve a look's completeness score.
COMPLETENESS_WEIGHTS: dict[Slot, int] = {"footwear": 2, "accessory": 1}


@dataclass(frozen=True)
class ProductImage:
    """One garment asset, addressed the ways the vendor accepts it.

    `RunClothV4Task` accepts a reference as either `ref_file_id` (an image we
    uploaded through the File API) or `ref_file_url` (a publicly reachable URL).
    A product already present in YouCam storage fills `file_id`; one linked from
    a partner feed fills `url`; an item in the bundled demo catalogue fills
    `local_path` and is uploaded on first use.

    `local_path` is deliberately *not* usable as-is. YouCam has to fetch the
    garment from somewhere it can reach, so a local asset must be pushed through
    the File API to obtain a `file_id` - see `services/tryon.py`.
    """

    file_id: str | None = None
    url: str | None = None
    content_type: str | None = None
    #: Filename inside `app/catalog/assets/`, set for bundled demo products.
    local_path: str | None = None

    @property
    def is_usable(self) -> bool:
        """True when the vendor can already be handed this image."""
        return bool(self.file_id or self.url)

    @property
    def needs_upload(self) -> bool:
        """True when the image must be pushed through the File API first."""
        return not self.is_usable and bool(self.local_path)

    @property
    def is_tryon_capable(self) -> bool:
        """True when some path to a V4.0 reference exists."""
        return self.is_usable or self.needs_upload


@dataclass(frozen=True)
class Product:
    """A garment LOOKLOCK can recommend and put on a person."""

    product_id: str
    name: str
    slot: Slot
    image: ProductImage
    #: INR, whole rupees. The UI formats this; the engine only compares it.
    price_inr: int
    #: Primary style first; later entries describe secondary affinity.
    styles: tuple[Style, ...]
    occasions: tuple[Occasion, ...]
    description: str
    #: Human-readable colour name, shown on the product card.
    color: str
    #: Only set when the source knows it. The engine can classify the garment
    #: itself when passed `auto`, so this is a hint, not a requirement.
    garment_category: GarmentCategory | None = None
    brand: str | None = None
    #: Where a shopper would go. Display-only. Always `None` in the demo
    #: catalogue: inventing retailer links would misrepresent products that do
    #: not exist, so the UI says "demo product" instead.
    purchase_url: str | None = None

    @property
    def primary_style(self) -> Style | None:
        return self.styles[0] if self.styles else None

    @property
    def is_tryon_capable(self) -> bool:
        """Accessories are display-only; they never become a try-on reference."""
        return self.slot != "accessory" and self.image.is_tryon_capable

    @property
    def is_demo(self) -> bool:
        """True when no real retailer listing backs this item."""
        return self.purchase_url is None

    def matches_style(self, style: Style) -> bool:
        return style in self.styles

    def matches_occasion(self, occasion: Occasion) -> bool:
        return occasion in self.occasions


@runtime_checkable
class ProductSource(Protocol):
    """Read-only lookup over whatever catalogue we end up using."""

    async def get(self, product_id: str) -> Product | None:
        """Return one product, or `None` if it is unknown or unavailable."""
        ...

    async def all(self) -> Sequence[Product]:
        """Return the full catalogue. Used to build recommendation rounds."""
        ...

    async def search(
        self,
        query: str,
        *,
        garment_category: GarmentCategory | None = None,
        limit: int = 20,
    ) -> Sequence[Product]:
        """Return candidate products for a recommendation round."""
        ...


class ProductNotFoundError(LookupError):
    """Raised when a caller needs a product that the source cannot supply."""


def require_reference(product: Product) -> ProductImage:
    """Return the garment image a V4.0 try-on needs, or fail loudly.

    Guarding here keeps the "no image means no request" rule in one place rather
    than relying on every caller to remember it. Accessories are rejected too:
    they are catalogue decoration, not something we can dress a person in.
    """
    if product.slot == "accessory":
        raise ProductNotFoundError(
            f"Product {product.product_id!r} is an accessory, which is display-only "
            "and cannot be sent to AI Clothes Virtual Try-On V4.0."
        )
    if not product.image.is_tryon_capable:
        raise ProductNotFoundError(
            f"Product {product.product_id!r} has no garment image, so it cannot "
            "be sent to AI Clothes Virtual Try-On V4.0."
        )
    return product.image
