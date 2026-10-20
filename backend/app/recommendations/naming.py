"""Naming recommended looks and deciding how to picture them.

Two jobs, both of which exist because a recommendation the shopper cannot picture
is not a recommendation.

**Naming.** A look is a set of products, and showing a shopper five garment names
tells them nothing about the outfit. Each look gets one short editorial name
derived from the look's own contents - the occasion it was built for, the
signature piece, and the pairing when that is what distinguishes it. Nothing is
random and nothing is written per-product by hand, so a new provider produces
sensible names on the first run.

**Visual strategy.** A look card must show an outfit, not one garment. Three
sources of a picture are possible and the order matters:

1. a *styled* shot the provider supplied - a real image of the garment being worn.
   This is the only option that is genuinely a photograph of the outfit;
2. a composite assembled from the actual product images in the look. This is a
   composition of real product photography, not a generated garment, which is why
   it is honest to show;
3. nothing usable, in which case the UI falls back to a plain product grid and says
   the images are missing rather than inventing a picture.

Explicitly *not* offered: generating a picture of the outfit. That would be a
fabrication of the thing the shopper is about to buy, and it would be
indistinguishable in the UI from a real retailer's photograph.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.product import Occasion, Product, Slot

VisualKind = Literal["complete_look", "composite", "grid"]

#: How a look should be pictured. The UI reads `kind` to decide whether to render
#: one image, a layered composition, or a grid.
#:
#: `image_url` is populated only for `complete_look`, where it is a real styled
#: photograph from the provider. For `composite` the picture is assembled from
#: `layers` on the client, each of which is a real product image.
class LookVisual(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: VisualKind
    #: Only for `complete_look`.
    image_url: str | None = None
    layers: tuple[VisualLayer, ...] = ()
    #: Whether any imagery here is a real listing photograph.
    demo_imagery: bool = True
    #: Explains the visual to the shopper in words, for `aria-label` and captions.
    alt: str = ""


class VisualLayer(BaseModel):
    """One garment's image, and where it sits in the composition.

    The offsets are fractions of the composition box and are deliberately
    overlapping: a layered outfit is garments on top of each other, and the
    back-to-front order is the dressing order.
    """

    model_config = ConfigDict(frozen=True)

    product_id: str
    slot: Slot
    image_url: str
    alt: str
    #: 0..1, larger is a bigger presence in the frame.
    scale: float = Field(ge=0.0, le=1.0)
    #: Horizontal anchor within the composition box.
    x: float = Field(ge=0.0, le=1.0)
    vertical: bool = False


#: How a garment's `subcategory` maps onto an editorial *family*, and what that
#: family is called in a look's name.
#:
#: The family exists because naming a look from its subcategory alone produces
#: nonsense: "Ceremonial Oxford Shirt" for a wedding is an oxford shirt, not a
#: ceremonial garment, and the shopper rightly distrusts a name like that. Ceremonial
#: families keep their own noun because "Ceremonial Sherwani" is exactly right;
#: the quietly occasion-specific families take a generic noun and get their
#: character from the epithet instead.
_FAMILY: dict[str, tuple[str, str]] = {
    "sherwani": ("ceremonial", ""),
    "bandhgala": ("ceremonial", ""),
    "nehru jacket": ("ceremonial", ""),
    "kurta": ("ceremonial", ""),
    "bandhgala jacket": ("ceremonial", ""),
    "brocade jacket": ("ceremonial", ""),
    "blazer": ("tailoring", "Tailoring"),
    "overcoat": ("outerwear", "Outerwear"),
    "safari jacket": ("casual_layer", "Layers"),
    "trucker jacket": ("casual_layer", "Layers"),
    "dress shirt": ("shirting", "Shirting"),
    "oxford shirt": ("shirting", "Shirting"),
    "churidar": ("ethnic_bottom", "Churidar"),
    "formal trouser": ("trousers", "Trousers"),
    "casual trouser": ("trousers", "Trousers"),
    "a-line skirt": ("skirts", "Skirts"),
    "wrap skirt": ("skirts", "Skirts"),
    "mojari": ("footwear", "Footwear"),
    "oxford": ("footwear", "Footwear"),
    "derby": ("footwear", "Footwear"),
    "chelsea boot": ("footwear", "Footwear"),
}

#: Fallback noun for a product whose `subcategory` is missing or unrecognised.
_GENERIC_ARCHETYPE: dict[Slot, str] = {
    # Placeholder nouns, used only when a product has no usable `subcategory`.
    # They are real garment names rather than slot labels: a look name is
    # shopper-facing copy, and "Ceremonial Top" reads as a bug where
    # "Ceremonial Shirting" reads as copy.
    "top": "Shirting",
    "bottom": "Trousers",
    "outerwear": "Outerwear",
    "footwear": "Footwear",
    "accessory": "Finishing Touch",
}

#: The occasion's own register, used when a family has no opinion of its own.
_OCCASION_EPITHET: dict[Occasion, str] = {
    "Wedding": "Ceremonial",
    "Party": "After-Dark",
    "Date Night": "Evening",
    "Interview": "Boardroom",
    "Casual": "Off-Duty",
    "Vacation": "Coastal",
}

#: Per-family register, where a family is only worn in some settings.
_FAMILY_EPITHET: dict[str, dict[Occasion, str]] = {
    "ceremonial": {
        "Wedding": "Ceremonial",
        "Party": "After-Dark",
        "Date Night": "Evening",
        "Interview": "Formal",
        "Casual": "Festive",
        "Vacation": "Festive",
    },
    "tailoring": {
        "Wedding": "Evening",
        "Party": "After-Dark",
        "Date Night": "Date Night",
        "Interview": "Boardroom",
        "Casual": "Off-Duty",
        "Vacation": "Coastal",
    },
    "shirting": {
        "Wedding": "Quiet",
        "Party": "Evening",
        "Date Night": "Date Night",
        "Interview": "Boardroom",
        "Casual": "Off-Duty",
        "Vacation": "Coastal",
    },
    "casual_layer": {
        "Wedding": "Festive",
        "Party": "Weekend",
        "Date Night": "Off-Duty",
        "Interview": "Off-Duty",
        "Casual": "Off-Duty",
        "Vacation": "Coastal",
    },
    "outerwear": {
        "Wedding": "Evening",
        "Party": "After-Dark",
        "Date Night": "Date Night",
        "Interview": "Boardroom",
        "Casual": "Off-Duty",
        "Vacation": "Coastal",
    },
    "ethnic_bottom": {
        "Wedding": "Wedding",
        "Party": "Party",
        "Date Night": "Evening",
        "Interview": "Formal",
        "Casual": "Off-Duty",
        "Vacation": "Holiday",
    },
    "trousers": {
        "Wedding": "Wedding",
        "Party": "Party",
        "Date Night": "Dinner",
        "Interview": "Boardroom",
        "Casual": "Off-Duty",
        "Vacation": "Coastal",
    },
    "skirts": {
        "Wedding": "Wedding",
        "Party": "Party",
        "Date Night": "Dinner",
        "Interview": "Boardroom",
        "Casual": "Off-Duty",
        "Vacation": "Coastal",
    },
    "footwear": {
        "Wedding": "Ceremonial",
        "Party": "After-Dark",
        "Date Night": "Evening",
        "Interview": "Boardroom",
        "Casual": "Off-Duty",
        "Vacation": "Coastal",
    },
}


def archetype(product: Product) -> str:
    """The one-word noun that names this product's kind of garment."""
    subcategory = (product.subcategory or "").strip()
    family = _FAMILY.get(subcategory.lower())
    if family is not None:
        return family[1] or subcategory
    return _GENERIC_ARCHETYPE.get(product.slot, "Piece")


def family_of(product: Product) -> str:
    """Which editorial family this garment belongs to.

    Falls back to the slot, so a product with no subcategory still gets a
    sensible register rather than being named after its placeholder.
    """
    subcategory = (product.subcategory or "").strip().lower()
    known = _FAMILY.get(subcategory)
    if known is not None:
        return known[0]
    return {
        "top": "shirting",
        "bottom": "trousers",
        "outerwear": "outerwear",
        "footwear": "footwear",
        "accessory": "accessory",
    }.get(product.slot, "generic")


def epithet_for(product: Product, occasion: Occasion) -> str:
    """The register word describing this garment at this occasion."""
    per_family = _FAMILY_EPITHET.get(family_of(product))
    if per_family is not None:
        return per_family.get(occasion, _OCCASION_EPITHET.get(occasion, "Curated"))
    return _OCCASION_EPITHET.get(occasion, "Curated")


def signature_for(items: Sequence[Product]) -> Product:
    """The garment a look should be named after.

    Priority runs from most to least defining: a ceremonial piece, then an outer
    layer, then the top. A wedding look built from a sherwani and a churidar is
    "Ceremonial Sherwani"; the same look described from its trousers would be
    "Ceremonial Trousers", which sells the wrong thing.
    """

    def rank(product: Product) -> int:
        family = family_of(product)
        if family == "ceremonial":
            return 0
        if product.slot == "outerwear":
            return 1
        if product.slot == "top":
            return 2
        return 3

    return min(items, key=rank)


def name_candidate(
    signature: Product, pairing: Product | None, occasion: Occasion
) -> str:
    """Build a look's name from the signature garment and the occasion.

    `pairing` is accepted for symmetry with `name_candidate_with_pairing`; the
    short form is deliberately independent of it so that two looks sharing a
    signature piece collide here and are resolved below rather than being silently
    distinguished by an arbitrary pairing.
    """
    noun = archetype(signature)
    return f"{epithet_for(signature, occasion)} {noun}".strip()


def name_candidate_with_pairing(
    signature: Product, pairing: Product | None, occasion: Occasion
) -> str:
    base = name_candidate(signature, pairing, occasion)
    if pairing is None:
        return base
    return f"{base} with {archetype(pairing)}"

#: How each slot is composed: scale, horizontal anchor, and whether it is drawn as
#: a hanging column (bodies) or a floored item (shoes, accessories).
_LAYOUT: dict[Slot, tuple[float, float, bool]] = {
    "top": (0.92, 0.5, True),
    "bottom": (0.78, 0.5, True),
    "outerwear": (1.0, 0.5, True),
    "footwear": (0.46, 0.5, False),
    "accessory": (0.26, 0.78, False),
}


def name_looks(
    signatures: list[tuple[Product, Product | None]], occasion: Occasion
) -> list[str]:
    """Name every look, guaranteeing the set has no duplicates.

    Uniqueness is *enforced*, not hoped for, because two cards with the same
    heading are indistinguishable in the results grid. Escalating in specificity:

    1. the short form - register plus family;
    2. plus the pairing, which is enough whenever the two looks share a signature
       piece but differ below the waist;
    3. plus the signature's colour, which distinguishes looks that share a garment
       type and a pairing;
    4. a numeric suffix, which is only reachable when two looks are genuinely the
       same outfit described twice - something the diversity constraint in
       `engine._select` is meant to prevent.

    Resolution happens across the whole chosen set rather than per-look, so the
    order of the results never depends on how many collisions happen to occur.
    """
    names: list[str] = []
    taken: set[str] = set()
    for signature, pairing in signatures:
        options = (
            name_candidate(signature, pairing, occasion),
            name_candidate_with_pairing(signature, pairing, occasion),
            f"{name_candidate(signature, pairing, occasion)} in {signature.color}",
        )
        chosen = next((option for option in options if option not in taken), None)
        if chosen is None:
            chosen = f"{options[-1]} ({len(taken) + 1})"
        names.append(chosen)
        taken.add(chosen)
    return names


def build_visual(
    items: list[tuple[Product, str]],
    *,
    has_styled_shot: str | None = None,
    look_name: str = "",
) -> LookVisual:
    """Decide how to picture a look.

    `items` is the look in dressing order, each paired with the URL its image is
    served from. `has_styled_shot`, when given, is the product whose
    `styled_image` shows the garment on a person; it wins over composition because
    a real worn photograph beats an arrangement of flats.
    """
    demo = all(product.is_demo for product, _ in items)
    if has_styled_shot is not None:
        return LookVisual(
            kind="complete_look",
            image_url=has_styled_shot,
            layers=(),
            demo_imagery=demo,
            alt=f"{look_name or 'This look'} worn as styled by the retailer",
        )

    layers: list[VisualLayer] = []
    for product, image_url in items:
        scale, x, vertical = _LAYOUT.get(product.slot, (0.5, 0.5, False))
        layers.append(
            VisualLayer(
                product_id=product.product_id,
                slot=product.slot,
                image_url=image_url,
                alt=f"{product.name} in {product.color}",
                scale=scale,
                x=x,
                vertical=vertical,
            )
        )

    if not layers:
        return LookVisual(
            kind="grid",
            image_url=None,
            layers=(),
            demo_imagery=demo,
            alt=look_name or "This look has no imagery available",
        )

    return LookVisual(
        kind="composite",
        image_url=None,
        layers=tuple(layers),
        demo_imagery=demo,
        alt=(
            f"{look_name or 'This look'} composed from "
            f"{len(layers)} product image{'s' if len(layers) != 1 else ''}"
        ),
    )
