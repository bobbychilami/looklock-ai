"""The bundled demo catalogue.

Every product here is fictional. Prices, names and descriptions exist to make the
recommendation engine and the shopping-breakdown screen behave realistically.

The important rule is what is *absent*: `purchase_url` and `retailer` are both
`None`, because no storefront anywhere sells these items. `Product.can_shop` is
therefore `False` for the entire catalogue and the UI renders an explicit demo
state instead of a buy button. A demo catalogue that invented plausible URLs would
look more finished in a screenshot and be a lie in a checkout flow. When a real
provider is registered its products carry real URLs and the same UI starts
producing real "Shop at <Retailer>" links with no change to any component.

`retailer` being `None` while `brand` is set is not an inconsistency: `brand` is
the fictional house that designed the garment ("LOOKLOCK Studio"), `retailer` is
who sells it. There is no second party in a demo catalogue.

`category` and `subcategory` are LOOKLOCK's own merchandising taxonomy, applied
during seeding the way a PIM would apply it. No retailer publishes them, which is
part of why a provider has to normalise into `Product` rather than pass a vendor
payload through.

`garment_category` is the hint handed to AI Clothes Virtual Try-On V4.0. It maps
1:1 onto the vendor's enum, is derived from the outfit slot rather than written by
hand, and is deliberately not `auto`, so a mislabelled item shows up as a visibly
wrong try-on rather than a silently plausible one. Accessories get no mapping
because they are never sent to the service at all.

Images are the original renders produced by
`backend/tools/generate_catalog_assets.py`. Each `local_path` below must exist in
`app/catalog/assets/`; `tests/test_catalog.py` enforces that so the catalogue
cannot drift away from its artwork.
"""

from __future__ import annotations

from dataclasses import replace

from app.catalog.product import Product, ProductImage
from app.services.youcam.schemas import GarmentCategory

#: The fictional design house behind every demo item. Never a retailer.
_LOOKLOCK = "LOOKLOCK Studio"

#: Which V4.0 `garment_category` each outfit slot maps to.
#:
#: Derived from the slot rather than written on all 35 products. The mapping is a
#: pure function of the slot, and spelling it out per product is exactly how a
#: hand-maintained catalogue ends up with one kurta labelled `shoes` while every
#: test that checks the enum still passes. A provider supplies its own mapping
#: from whatever its vendor calls these; this is only the demo catalogue's.
_SLOT_GARMENT_CATEGORY: dict[str, GarmentCategory] = {
    "top": "upper_body",
    "bottom": "lower_body",
    "outerwear": "outer",
    "footwear": "shoes",
}

# fmt: off
_UPPER: tuple[Product, ...] = (
    Product(
        product_id="upper-ivory-sherwani",
        name="Ivory Silk Sherwani",
        slot="top",
        image=ProductImage(local_path="ivory-sherwani.png"),
        price_inr=14500,
        styles=("Classic", "Bold"),
        occasions=("Wedding", "Party"),
        color="Ivory",
        category="Ethnic Wear",
        subcategory="Sherwani",
        colors=("Ivory", "Champagne", "Gold"),
        brand=_LOOKLOCK,
        description=(
            "A long, structured sherwani in fluid ivory silk, with a mandarin placket "
            "and a clean shoulder line."
        ),
    ),
    Product(
        product_id="upper-ivory-bandhgala",
        name="Ivory Bandhgala",
        slot="top",
        image=ProductImage(local_path="ivory-bandhgala.png"),
        price_inr=12900,
        styles=("Classic",),
        occasions=("Wedding",),
        color="Ivory",
        category="Ethnic Wear",
        subcategory="Bandhgala",
        colors=("Ivory", "Cream"),
        brand=_LOOKLOCK,
        description=(
            "The formal bandhgala, cut close through the chest with a banded collar "
            "for a distinctly ceremonial finish."
        ),
    ),
    Product(
        product_id="upper-cream-kurta",
        name="Chikankari Cotton Kurta",
        slot="top",
        image=ProductImage(local_path="cream-kurta.png"),
        price_inr=3900,
        styles=("Minimal", "Classic"),
        occasions=("Casual", "Party", "Vacation"),
        color="Cream",
        category="Ethnic Wear",
        subcategory="Kurta",
        colors=("Cream", "White", "Powder Blue"),
        brand=_LOOKLOCK,
        description=(
            "An easy cotton kurta with a relaxed hem - the quiet option when the "
            "occasion does not need ceremony."
        ),
    ),
    Product(
        product_id="upper-rust-sherwani",
        name="Rust Raw Silk Sherwani",
        slot="top",
        image=ProductImage(local_path="rust-sherwani.png"),
        price_inr=16500,
        styles=("Bold", "Classic"),
        occasions=("Wedding", "Party"),
        color="Rust",
        category="Ethnic Wear",
        subcategory="Sherwani",
        colors=("Rust", "Maroon", "Bottle Green"),
        brand=_LOOKLOCK,
        description=(
            "Deep rust raw silk with gold-toned buttons, for the wedding guest who "
            "would rather not dress like everyone else."
        ),
    ),
    Product(
        product_id="upper-indigo-blazer",
        name="Indigo Linen Blazer",
        slot="top",
        image=ProductImage(local_path="indigo-blazer.png"),
        price_inr=7800,
        styles=("Modern", "Minimal"),
        occasions=("Interview", "Casual", "Vacation"),
        color="Indigo",
        category="Tailoring",
        subcategory="Blazer",
        colors=("Indigo", "Navy", "Sand"),
        brand=_LOOKLOCK,
        description=(
            "An unstructured linen blazer with a notched lapel - tailored, but not "
            "severe."
        ),
    ),
    Product(
        product_id="upper-charcoal-blazer",
        name="Charcoal Wool Blazer",
        slot="top",
        image=ProductImage(local_path="charcoal-blazer.png"),
        price_inr=8600,
        styles=("Classic", "Modern"),
        occasions=("Interview", "Date Night"),
        color="Charcoal",
        category="Tailoring",
        subcategory="Blazer",
        colors=("Charcoal", "Black", "Mid Grey"),
        brand=_LOOKLOCK,
        description=(
            "A single-breasted wool blazer with a soft shoulder, cut to sit cleanly "
            "over a shirt or alone."
        ),
    ),
    Product(
        product_id="upper-teal-jacket",
        name="Deep Teal Nehru Jacket",
        slot="top",
        image=ProductImage(local_path="teal-jacket.png"),
        price_inr=9400,
        styles=("Bold", "Modern"),
        occasions=("Wedding", "Party"),
        color="Deep Teal",
        category="Ethnic Wear",
        subcategory="Nehru Jacket",
        colors=("Deep Teal", "Emerald", "Midnight Blue"),
        brand=_LOOKLOCK,
        description=(
            "A collarless Nehru jacket in deep teal, worn over a kurta or shirt to "
            "lift a plain outfit."
        ),
    ),
    Product(
        product_id="upper-ivory-shirt",
        name="Ivory Poplin Shirt",
        slot="top",
        image=ProductImage(local_path="ivory-shirt.png"),
        price_inr=1400,
        styles=("Minimal", "Classic"),
        occasions=("Interview", "Casual", "Date Night", "Vacation"),
        color="Ivory",
        category="Shirts",
        subcategory="Dress Shirt",
        colors=("Ivory", "White", "Sky Blue"),
        brand=_LOOKLOCK,
        description=(
            "Crisp poplin with a soft collar, the workhorse that suits an interview "
            "and a dinner equally well."
        ),
    ),
    Product(
        product_id="upper-mist-shirt",
        name="Grey Oxford Shirt",
        slot="top",
        image=ProductImage(local_path="mist-shirt.png"),
        price_inr=1900,
        styles=("Classic", "Minimal"),
        occasions=("Interview", "Casual"),
        color="Grey",
        category="Shirts",
        subcategory="Oxford Shirt",
        colors=("Grey", "White", "Navy"),
        brand=_LOOKLOCK,
        description=(
            "A mid-grey oxford with a soft roll, easy under a blazer or by itself."
        ),
    ),
    Product(
        product_id="upper-plum-shirt",
        name="Plum Oxford Shirt",
        slot="top",
        image=ProductImage(local_path="plum-shirt.png"),
        price_inr=2100,
        styles=("Modern", "Bold"),
        occasions=("Date Night", "Party"),
        color="Plum",
        category="Shirts",
        subcategory="Oxford Shirt",
        colors=("Plum", "Burgundy", "Navy"),
        brand=_LOOKLOCK,
        description=(
            "A deep plum oxford that reads as considered rather than loud, with "
            "enough colour to anchor a neutral outfit."
        ),
    ),
    # The two cheapest pieces in the catalogue. They exist so the ₹2,000 budget
    # preset can actually produce an in-budget outfit: without a sub-₹1,000 top
    # and bottom, the cheapest complete look in the range costs more than the
    # smallest preset the onboarding UI offers, and every shopper who picked it
    # would be told their own budget was unachievable.
    Product(
        product_id="upper-cream-mandarin",
        name="Cotton Mandarin Shirt",
        slot="top",
        image=ProductImage(local_path="cream-mandarin.png"),
        price_inr=850,
        styles=("Minimal",),
        occasions=("Casual", "Vacation"),
        color="Cream",
        category="Shirts",
        subcategory="Mandarin Shirt",
        colors=("Cream", "White", "Sage"),
        brand=_LOOKLOCK,
        description=(
            "A band-collared cotton shirt with a straight hem - warm-weather dressing "
            "at its least complicated."
        ),
    ),
)

_LOWER: tuple[Product, ...] = (
    Product(
        product_id="lower-ivory-churidar",
        name="Ivory Churidar",
        slot="bottom",
        image=ProductImage(local_path="ivory-churidar.png"),
        price_inr=1500,
        styles=("Classic",),
        occasions=("Wedding", "Party"),
        color="Ivory",
        category="Ethnic Wear",
        subcategory="Churidar",
        colors=("Ivory", "Cream", "Gold"),
        brand=_LOOKLOCK,
        description=(
            "A fitted gathered churidar in ivory, the traditional pairing for a "
            "sherwani or bandhgala."
        ),
    ),
    Product(
        product_id="lower-cream-churidar",
        name="Cream Churidar",
        slot="bottom",
        image=ProductImage(local_path="cream-churidar.png"),
        price_inr=1300,
        styles=("Minimal",),
        occasions=("Casual", "Party", "Vacation"),
        color="Cream",
        category="Ethnic Wear",
        subcategory="Churidar",
        colors=("Cream", "White", "Sage"),
        brand=_LOOKLOCK,
        description=(
            "The same gathered cut in a softer cream, for daytime and less formal "
            "evenings."
        ),
    ),
    Product(
        product_id="lower-ink-trousers",
        name="Ink Stretch Trousers",
        slot="bottom",
        image=ProductImage(local_path="ink-trousers.png"),
        price_inr=2600,
        styles=("Modern", "Minimal"),
        occasions=("Interview", "Date Night", "Vacation"),
        color="Ink",
        category="Trousers",
        subcategory="Formal Trouser",
        colors=("Ink", "Black", "Charcoal"),
        brand=_LOOKLOCK,
        description=(
            "Flat-front stretch trousers in ink, with a clean break and enough give "
            "to sit through a long evening."
        ),
    ),
    Product(
        product_id="lower-charcoal-trousers",
        name="Charcoal Formal Trousers",
        slot="bottom",
        image=ProductImage(local_path="charcoal-trousers.png"),
        price_inr=2900,
        styles=("Classic", "Modern"),
        occasions=("Interview",),
        color="Charcoal",
        category="Trousers",
        subcategory="Formal Trouser",
        colors=("Charcoal", "Black", "Navy"),
        brand=_LOOKLOCK,
        description=(
            "A sharp, high-waisted trouser with a pressed crease - the safest answer "
            "to an interview."
        ),
    ),
    Product(
        product_id="lower-slate-trousers",
        name="Slate Casual Trousers",
        slot="bottom",
        image=ProductImage(local_path="slate-trousers.png"),
        price_inr=2400,
        styles=("Modern",),
        occasions=("Casual", "Date Night", "Vacation"),
        color="Slate",
        category="Trousers",
        subcategory="Casual Trouser",
        colors=("Slate", "Olive", "Stone"),
        brand=_LOOKLOCK,
        description=(
            "Relaxed slate trousers with a soft drape, comfortable enough for an "
            "evening that turns into late."
        ),
    ),
    Product(
        product_id="lower-teal-trousers",
        name="Deep Teal Trousers",
        slot="bottom",
        image=ProductImage(local_path="teal-trousers.png"),
        price_inr=3100,
        styles=("Modern", "Bold"),
        occasions=("Date Night", "Party"),
        color="Deep Teal",
        category="Trousers",
        subcategory="Formal Trouser",
        colors=("Deep Teal", "Forest Green", "Rust"),
        brand=_LOOKLOCK,
        description=(
            "Deep teal tailoring that carries a colour without shouting, made to "
            "match a plain shirt."
        ),
    ),
    Product(
        product_id="lower-charcoal-skirt",
        name="Charcoal A-Line Skirt",
        slot="bottom",
        image=ProductImage(local_path="charcoal-skirt.png"),
        price_inr=2700,
        styles=("Classic", "Minimal"),
        occasions=("Interview", "Casual"),
        color="Charcoal",
        category="Skirts",
        subcategory="A-Line Skirt",
        colors=("Charcoal", "Black", "Navy"),
        brand=_LOOKLOCK,
        description=(
            "A structured A-line skirt in charcoal - a polished alternative to "
            "tailoring for the office."
        ),
    ),
    Product(
        product_id="lower-mist-skirt",
        name="Mist Wrap Skirt",
        slot="bottom",
        image=ProductImage(local_path="mist-skirt.png"),
        price_inr=2400,
        styles=("Minimal",),
        occasions=("Casual", "Date Night", "Vacation"),
        color="Mist",
        category="Skirts",
        subcategory="Wrap Skirt",
        colors=("Mist", "Sage", "Sand"),
        brand=_LOOKLOCK,
        description=(
            "A soft wrap skirt in mist grey, with an easy drape and no fastenings."
        ),
    ),
    # Paired with the mandarin shirt above to make the catalogue's cheapest
    # wearable outfit. See the note on `upper-cream-mandarin`.
    Product(
        product_id="lower-cream-drawstring",
        name="Cotton Drawstring Trousers",
        slot="bottom",
        image=ProductImage(local_path="cream-drawstring.png"),
        price_inr=750,
        styles=("Minimal",),
        occasions=("Casual", "Vacation"),
        color="Cream",
        category="Trousers",
        subcategory="Casual Trouser",
        colors=("Cream", "Sand", "Olive"),
        brand=_LOOKLOCK,
        description=(
            "A drawstring cotton trouser with an elastic back waist - the most "
            "comfortable thing in the range to sit in all afternoon."
        ),
    ),
)

# Outerwear is a worn garment, so it counts towards the occasion and style scores
# and towards completeness - unlike accessories, which are display-only. It is not
# pre-filtered by occasion the way accessories are, because a jacket genuinely
# changes whether a look suits the evening.
_OUTERWEAR: tuple[Product, ...] = (
    Product(
        product_id="outer-ivory-bandhgala-jacket",
        name="Ivory Bandhgala Jacket",
        slot="outerwear",
        image=ProductImage(local_path="ivory-bandhgala-jacket.png"),
        price_inr=6800,
        styles=("Classic",),
        occasions=("Wedding", "Party"),
        color="Ivory",
        category="Ethnic Wear",
        subcategory="Bandhgala Jacket",
        colors=("Ivory", "Champagne"),
        brand=_LOOKLOCK,
        description=(
            "A long brocade bandhgala jacket in ivory, the traditional outer layer "
            "worn open over a churidar."
        ),
    ),
    Product(
        product_id="outer-rust-brocade-jacket",
        name="Rust Brocade Jacket",
        slot="outerwear",
        image=ProductImage(local_path="rust-brocade-jacket.png"),
        price_inr=7200,
        styles=("Bold", "Classic"),
        occasions=("Wedding", "Party"),
        color="Rust",
        category="Ethnic Wear",
        subcategory="Brocade Jacket",
        colors=("Rust", "Maroon"),
        brand=_LOOKLOCK,
        description=(
            "Rust brocade with a tonal jacquard and a deep collar, layered over ivory "
            "for a wedding with more colour in it."
        ),
    ),
    Product(
        product_id="outer-charcoal-wool-coat",
        name="Charcoal Wool Overcoat",
        slot="outerwear",
        image=ProductImage(local_path="charcoal-wool-coat.png"),
        price_inr=8900,
        styles=("Classic", "Minimal"),
        occasions=("Interview", "Date Night"),
        color="Charcoal",
        category="Outerwear",
        subcategory="Overcoat",
        colors=("Charcoal", "Camel", "Black"),
        brand=_LOOKLOCK,
        description=(
            "A single-breasted wool overcoat with a notch collar, warm enough for a "
            "winter evening that runs late."
        ),
    ),
    Product(
        product_id="outer-cream-linen-jacket",
        name="Cream Linen Safari Jacket",
        slot="outerwear",
        image=ProductImage(local_path="cream-linen-jacket.png"),
        price_inr=4200,
        styles=("Minimal", "Modern"),
        occasions=("Vacation", "Casual"),
        color="Cream",
        category="Outerwear",
        subcategory="Safari Jacket",
        colors=("Cream", "Sand", "Olive"),
        brand=_LOOKLOCK,
        description=(
            "An unlined linen safari jacket with four patch pockets, the layer that "
            "makes warm-weather tailoring work."
        ),
    ),
    Product(
        product_id="outer-indigo-denim-jacket",
        name="Indigo Denim Trucker",
        slot="outerwear",
        image=ProductImage(local_path="indigo-denim-jacket.png"),
        price_inr=3600,
        styles=("Modern", "Bold"),
        occasions=("Casual", "Vacation", "Date Night"),
        color="Indigo",
        category="Outerwear",
        subcategory="Trucker Jacket",
        colors=("Indigo", "Mid Blue", "Washed Black"),
        brand=_LOOKLOCK,
        description=(
            "A structured denim trucker in deep indigo, sturdy enough to be the whole "
            "outfit."
        ),
    ),
)

_FOOTWEAR: tuple[Product, ...] = (
    Product(
        product_id="shoes-gold-mojari",
        name="Gold Zari Mojari",
        slot="footwear",
        image=ProductImage(local_path="gold-mojari.png"),
        price_inr=4200,
        styles=("Bold", "Classic"),
        occasions=("Wedding", "Party"),
        color="Gold",
        category="Footwear",
        subcategory="Mojari",
        colors=("Gold", "Champagne"),
        brand=_LOOKLOCK,
        description=(
            "Leather mojari with a zari-embroidered vamp, made for wedding floors."
        ),
    ),
    Product(
        product_id="shoes-cream-mojari",
        name="Ivory Mojari",
        slot="footwear",
        image=ProductImage(local_path="cream-mojari.png"),
        price_inr=2900,
        styles=("Classic", "Minimal"),
        occasions=("Wedding", "Casual"),
        color="Ivory",
        category="Footwear",
        subcategory="Mojari",
        colors=("Ivory", "Cream"),
        brand=_LOOKLOCK,
        description="A plain ivory mojari with a light embroidered vamp.",
    ),
    Product(
        product_id="shoes-charcoal-derby",
        name="Charcoal Oxford",
        slot="footwear",
        image=ProductImage(local_path="charcoal-derby.png"),
        price_inr=5400,
        styles=("Classic", "Modern"),
        occasions=("Interview", "Date Night"),
        color="Charcoal",
        category="Footwear",
        subcategory="Oxford",
        colors=("Charcoal", "Brown", "Black"),
        brand=_LOOKLOCK,
        description=(
            "A closed-lace Oxford in charcoal, the most versatile shoe in the range."
        ),
    ),
    Product(
        product_id="shoes-ivory-derby",
        name="Ivory Derby",
        slot="footwear",
        image=ProductImage(local_path="ivory-derby.png"),
        price_inr=6200,
        styles=("Classic", "Minimal"),
        occasions=("Wedding", "Date Night", "Vacation"),
        color="Ivory",
        category="Footwear",
        subcategory="Derby",
        colors=("Ivory", "Sand", "Tan"),
        brand=_LOOKLOCK,
        description="An ivory derby with a slim sole, for a light summer occasion.",
    ),
    Product(
        product_id="shoes-ink-boot",
        name="Ink Chelsea Boot",
        slot="footwear",
        image=ProductImage(local_path="ink-boot.png"),
        price_inr=7800,
        styles=("Modern", "Bold"),
        occasions=("Casual", "Date Night"),
        color="Ink",
        category="Footwear",
        subcategory="Chelsea Boot",
        colors=("Ink", "Black", "Chestnut"),
        brand=_LOOKLOCK,
        description="A clean Chelsea boot in ink, for a sharper everyday silhouette.",
    ),
)

# Accessories are display-only. They complete a look and they appear in the
# shopping breakdown, but they are never sent to the try-on service.
_ACCESSORIES: tuple[Product, ...] = (
    Product(
        product_id="accessory-gold-belt",
        name="Leather Belt",
        slot="accessory",
        image=ProductImage(local_path="gold-belt.png"),
        price_inr=1600,
        styles=("Classic", "Modern"),
        occasions=("Interview", "Casual"),
        color="Brown",
        category="Accessories",
        subcategory="Belt",
        colors=("Brown", "Tan", "Black"),
        brand=_LOOKLOCK,
        description="A brown leather belt with a brushed gold buckle.",
    ),
    Product(
        product_id="accessory-gold-watch",
        name="Champagne Watch",
        slot="accessory",
        image=ProductImage(local_path="gold-watch.png"),
        price_inr=8900,
        styles=("Modern", "Classic"),
        occasions=("Interview", "Date Night"),
        color="Champagne",
        category="Accessories",
        subcategory="Wristwatch",
        colors=("Champagne", "Silver", "Gold"),
        brand=_LOOKLOCK,
        description="A slim champagne-dial watch on a brown leather strap.",
    ),
    Product(
        product_id="accessory-pocket-square",
        name="Ivory Pocket Square",
        slot="accessory",
        image=ProductImage(local_path="cream-pocket-square.png"),
        price_inr=700,
        styles=("Classic",),
        occasions=("Wedding", "Interview"),
        color="Ivory",
        category="Accessories",
        subcategory="Pocket Square",
        colors=("Ivory", "Cream", "White"),
        brand=_LOOKLOCK,
        description="An ivory pocket square, the detail that finishes a formal jacket.",
    ),
    Product(
        product_id="accessory-gold-necklace",
        name="Gold Necklace",
        slot="accessory",
        image=ProductImage(local_path="gold-necklace.png"),
        price_inr=5400,
        styles=("Bold",),
        occasions=("Wedding", "Party"),
        color="Gold",
        category="Accessories",
        subcategory="Necklace",
        colors=("Gold", "Champagne"),
        brand=_LOOKLOCK,
        description="A fine gold chain with a small pendant.",
    ),
    Product(
        product_id="accessory-cream-cuff",
        name="Ivory Cuff",
        slot="accessory",
        image=ProductImage(local_path="cream-cuff.png"),
        price_inr=1200,
        styles=("Minimal", "Classic"),
        occasions=("Interview", "Date Night"),
        color="Ivory",
        category="Accessories",
        subcategory="Cufflinks",
        colors=("Ivory", "White", "Champagne"),
        brand=_LOOKLOCK,
        description="An ivory cuff with four mother-of-pearl buttons.",
    ),
)
# fmt: on

CATALOGUE: tuple[Product, ...] = tuple(
    # `.get`, not `[]`: accessories have no entry because they are never sent to
    # the try-on service, so their category has no correct value.
    replace(product, garment_category=_SLOT_GARMENT_CATEGORY.get(product.slot))
    for product in (_UPPER + _LOWER + _OUTERWEAR + _FOOTWEAR + _ACCESSORIES)
)
