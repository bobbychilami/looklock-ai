"""The bundled demo catalogue.

Every product here is fictional. Prices, names and descriptions exist to make the
recommendation engine and the shopping-breakdown screen behave realistically, and
none of it is backed by a real retailer, so nothing in here should be presented as
a purchasable listing. `Product.is_demo` drives that labelling in the UI.

Images are the original flats rendered by `backend/tools/generate_catalog_assets.py`.
Each filename below must exist in `app/catalog/assets/`; `tests/test_catalog.py`
enforces that so the catalogue cannot drift away from its artwork.

`garment_category` is the hint handed to AI Clothes Virtual Try-On V4.0. It maps
1:1 onto the vendor's enum and is deliberately not `auto`, so a mislabelled item
shows up as a visibly wrong try-on rather than a silently plausible one.
"""

from __future__ import annotations

from app.catalog.product import Product, ProductImage

_LOOKLOCK = "LOOKLOCK Studio"

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
        garment_category="upper_body",
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
        garment_category="upper_body",
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
        occasions=("Casual", "Party"),
        color="Cream",
        garment_category="upper_body",
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
        garment_category="upper_body",
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
        occasions=("Interview", "Casual"),
        color="Indigo",
        garment_category="upper_body",
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
        garment_category="upper_body",
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
        garment_category="upper_body",
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
        occasions=("Interview", "Casual", "Date Night"),
        color="Ivory",
        garment_category="upper_body",
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
        garment_category="upper_body",
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
        garment_category="upper_body",
        brand=_LOOKLOCK,
        description=(
            "A deep plum oxford that reads as considered rather than loud, with "
            "enough colour to anchor a neutral outfit."
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
        garment_category="lower_body",
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
        occasions=("Casual", "Party"),
        color="Cream",
        garment_category="lower_body",
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
        occasions=("Interview", "Date Night"),
        color="Ink",
        garment_category="lower_body",
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
        garment_category="lower_body",
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
        occasions=("Casual", "Date Night"),
        color="Slate",
        garment_category="lower_body",
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
        garment_category="lower_body",
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
        garment_category="lower_body",
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
        occasions=("Casual", "Date Night"),
        color="Mist",
        garment_category="lower_body",
        brand=_LOOKLOCK,
        description=(
            "A soft wrap skirt in mist grey, with an easy drape and no fastenings."
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
        garment_category="shoes",
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
        garment_category="shoes",
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
        garment_category="shoes",
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
        occasions=("Wedding", "Date Night"),
        color="Ivory",
        garment_category="shoes",
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
        garment_category="shoes",
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
        brand=_LOOKLOCK,
        description="An ivory cuff with four mother-of-pearl buttons.",
    ),
)
# fmt: on

CATALOGUE: tuple[Product, ...] = _UPPER + _LOWER + _FOOTWEAR + _ACCESSORIES
