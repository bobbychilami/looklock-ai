"""Domain model for a LOOKLOCK product.

One shape for every product the app can show, no matter where it came from.

Three decisions shape this module.

1. **A product is a merchant listing, not a garment.** A retailer knows the price,
   the sizes, the colours and the page the thing is sold on. It does not know which
   occasion you are dressing for. Style and occasion tags therefore live here as
   *our* editorial judgement, not as vendor fields, which is why a provider is
   responsible for filling them in even when the retailer does not supply them.
2. **Buying and looking are different assets.** `image` is what a shopper is being
   shown; `vto_asset` is what AI Clothes Virtual Try-On V4.0 is handed. Retailers
   usually publish a lifestyle shot, a flat lay and sometimes a separate garment
   cut-out, and the cut-out is the one a try-on engine wants. Keeping them apart
   means a provider can supply a good merchandising image and a *different* try-on
   reference without either being compromised. See `VtoAsset`.
3. **Nothing about a listing is invented.** `retailer` and `purchase_url` are
   optional and mean exactly "we know this" - see `can_shop`. A demo or unverified
   product leaves them empty and the UI says so instead of linking somewhere that
   does not sell the thing.

`providers/` sits on top of this and is what the rest of the app talks to.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from app.services.youcam.schemas import GarmentCategory

#: Style axes offered during onboarding. Order is the order shown in the UI.
Style = Literal["Classic", "Modern", "Bold", "Minimal"]

#: Occasion axes offered during onboarding. Order is the order shown in the UI.
#:
#: A `Literal` rather than an `Enum` so the same tuple can drive a pydantic
#: request schema, the wizard's option list and the SQL-shaped filter in a
#: provider without three parallel sources of truth.
Occasion = Literal["Wedding", "Date Night", "Interview", "Party", "Casual", "Vacation"]


#: Where a garment sits in an outfit - the "category role".
#:
#: `top` and `bottom` are required to build a look. `outerwear`, `footwear` and
#: `accessory` are optional, which is what lets the engine score *completeness* as
#: a real ranking signal rather than a formality, and what allows genuinely low
#: budgets to still produce a wearable result instead of an empty shelf.
Slot = Literal["top", "bottom", "outerwear", "footwear", "accessory"]

SLOTS: tuple[Slot, ...] = ("top", "bottom", "outerwear", "footwear", "accessory")

#: Whether a listing can be bought right now, as the source describes it.
#:
#: `unknown` is the default rather than `out_of_stock` on purpose. A provider that
#: was not asked, or whose API omits the field, knows nothing - and claiming
#: "out of stock" would tell the shopper something untrue about a real listing.
#: Only a source that explicitly reports unavailability sets `out_of_stock`.
ProductAvailability = Literal["in_stock", "out_of_stock", "unknown"]

#: Slots without which a look is not an outfit.
REQUIRED_SLOTS: tuple[Slot, ...] = ("top", "bottom")

#: Ordered by how much they improve a look's completeness score.
COMPLETENESS_WEIGHTS: dict[Slot, int] = {"outerwear": 2, "footwear": 2, "accessory": 1}


@dataclass(frozen=True)
class ProductImage:
    """A merchandising image - the picture a shopper is judging the item by.

    `RunClothV4Task` accepts a reference as either `ref_file_id` (an image we
    uploaded through the File API) or `ref_file_url` (a publicly reachable URL),
    and a product already present in YouCam storage fills `file_id`; one linked
    from a retailer feed fills `url`; an item in the bundled demo catalogue fills
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
class VtoAsset:
    """A garment image chosen specifically to be sent to the try-on engine.

    Separate from `Product.image` on purpose. A retailer's hero shot is often a
    model on a styled set: it communicates the product to a human beautifully and
    confuses a generative engine, which is trying to transfer the *garment*. When
    a provider has a flat cut-out, that is the better reference and belongs here.
    """

    file_id: str | None = None
    url: str | None = None
    content_type: str | None = None
    local_path: str | None = None

    @property
    def is_usable(self) -> bool:
        return bool(self.file_id or self.url)

    @property
    def needs_upload(self) -> bool:
        return not self.is_usable and bool(self.local_path)

    @property
    def is_tryon_capable(self) -> bool:
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

    currency: str = "INR"
    category: str | None = None
    subcategory: str | None = None
    #: Every colourway the retailer lists, not just the one pictured.
    colors: tuple[str, ...] = ()
    #: Who sells it. `None` when the source is not a real storefront.
    retailer: str | None = None
    #: Where the shopper actually buys it. `None` unless genuinely verified.
    purchase_url: str | None = None
    #: Distinguishes direct retailer link vs Google Shopping product link.
    product_link_type: Literal["direct_retailer", "google_shopping"] | None = None
    #: Which provider answered, e.g. `shopping` or `amazon`. `None` for products built
    #: before this field existed.
    source: str | None = None
    #: The provider's own id for the listing - an Amazon ASIN, a Myntra product
    #: code. Kept verbatim rather than folded into `product_id` because it is the
    #: thing an affiliate link and a later `GetItems` call are actually keyed on.
    source_product_id: str | None = None
    #: Whether the source says this can be bought right now, and how confident that
    #: is. `None` means the source did not say, which is different from "no" and is
    #: rendered differently.
    availability: ProductAvailability = "unknown"
    #: The try-on engine's view of the garment; falls back to `image` when absent.
    vto_asset: VtoAsset | None = None
    #: A shot of the garment *being worn*, when the source publishes one.
    #:
    #: This is the only imagery in the model that can stand in for a complete-look
    #: photograph, and it is the reason `recommendations/naming.py` prefers it. It
    #: is deliberately not the default: a styled shot shows a model in a full
    #: outfit, so using it as *the* product image would attribute other garments
    #: to this product.
    styled_image: ProductImage | None = None
    #: Only set when the source knows it. The engine can classify the garment
    #: itself when passed `auto`, so this is a hint, not a requirement.
    garment_category: GarmentCategory | None = None
    brand: str | None = None

    @property
    def primary_style(self) -> Style | None:
        return self.styles[0] if self.styles else None

    @property
    def tryon_reference(self) -> ProductImage | VtoAsset | None:
        """The asset a V4.0 request should use.

        Prefers the dedicated `vto_asset` and falls back to the merchandising
        image, which is right for the demo catalogue where both are the same
        original render.
        """
        if self.vto_asset is not None and self.vto_asset.is_tryon_capable:
            return self.vto_asset
        if self.image.is_tryon_capable:
            return self.image
        return None

    @property
    def is_tryon_capable(self) -> bool:
        """Accessories are display-only; they never become a try-on reference."""
        return self.slot != "accessory" and self.tryon_reference is not None

    @property
    def tryon_uses_remote_image(self) -> bool:
        """True when the only try-on reference is a remote URL we do not control.

        A `file_id` (already in YouCam storage) or a `local_path` (a bundled asset
        we upload ourselves) is one we can hand to the engine with confidence. A
        plain `url` is a retailer's or CDN's image: the engine has to fetch it, and
        we cannot yet guarantee it will accept it. The UI keeps try-on disabled for
        those pieces rather than starting a job that fails at the vendor.
        """
        reference = self.tryon_reference
        if reference is None:
            return False
        if reference.file_id or reference.local_path:
            return False
        return bool(reference.url)

    @property
    def is_demo(self) -> bool:
        """True when no real retailer listing backs this item."""
        return self.purchase_url is None

    @property
    def has_styled_shot(self) -> str | None:
        """The URL of a worn shot of this garment, if the source published one."""
        if self.styled_image is None:
            return None
        return self.styled_image.url or self.styled_image.file_id

    @property
    def can_shop(self) -> bool:
        """True when there is a real page to send the shopper to.

        The single gate on every "Shop" affordance in the UI. A demo product has
        nothing to buy, and pretending otherwise with an invented URL is the one
        thing that would make this app a lie.

        Requires *both* fields. A provider that knows who sells an item but has no
        verified URL for it must not produce a half-working shop button, so the
        URL is the part that is genuinely load-bearing.
        """
        return bool(self.purchase_url) and bool(self.retailer)

    def matches_style(self, style: Style) -> bool:
        return style in self.styles

    def matches_occasion(self, occasion: Occasion) -> bool:
        return occasion in self.occasions

    def matches_color(self, color: str | None) -> bool:
        """Case-insensitive match against the pictured colour or any colourway."""
        if not color:
            return True
        needle = color.strip().lower()
        return any(needle in candidate.lower() for candidate in (self.color, *self.colors))


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


def require_reference(product: Product) -> ProductImage | VtoAsset:
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
    reference = product.tryon_reference
    if reference is None:
        raise ProductNotFoundError(
            f"Product {product.product_id!r} has no garment image, so it cannot "
            "be sent to AI Clothes Virtual Try-On V4.0."
        )
    return reference
