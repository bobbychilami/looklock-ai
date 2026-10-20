/**
 * Fixtures mirroring real backend responses.
 *
 * These were transcribed from the JSON the running API actually emits for
 * `POST /api/v1/recommendations` and `GET /api/v1/catalog/looks`, field for
 * field. Writing tests against a hand-invented shape is how a frontend drifts
 * from a contract it was never shown, so the captured values are used verbatim -
 * the ₹24,800 bandhgala, the `Ceremonial Bandhgala` name, the five composite
 * layers and the `demo_imagery: true` flag are all real.
 */

import type {
  CatalogueSummary,
  LookRecommendation,
  RecommendationResponse,
  ScoredProduct,
} from '@/api/types'

/** `GET /api/v1/catalog/looks`, verbatim. */
export const catalogueSummaryFixture: CatalogueSummary = {
  product_count: 35,
  counts_by_slot: { accessory: 5, bottom: 9, footwear: 5, outerwear: 5, top: 11 },
  occasions: ['Wedding', 'Date Night', 'Interview', 'Party', 'Casual', 'Vacation'],
  styles: ['Classic', 'Modern', 'Bold', 'Minimal'],
  budget_presets_inr: [2000, 5000, 8000, 15000, 25000],
  is_demo_catalogue: true,
  notice:
    'Every product here is a fictional demo item with an illustrative price. No retailer listing backs them, so there is nothing to buy and no external link to follow - the shopping panel says so rather than linking to a product page that does not exist.',
  provider_id: 'composite',
  provider_name: 'LOOKLOCK demo catalogue',
  supports_shopping: false,
  provider_available: true,
  provider_unavailable_reason: null,
  demo_imagery: true,
}

/**
 * One `ScoredProduct` exactly as the backend serialises it inside a look.
 *
 * Typed as `ScoredProduct` rather than inferred, so a field the backend is
 * missing cannot be quietly left out of a fixture: the compiler would object to
 * the incomplete object here, instead of the test failing later on a `undefined`
 * that happened to be tolerated.
 */
const bandhgala: ScoredProduct = {
  product_id: 'upper-ivory-bandhgala',
  name: 'Ivory Bandhgala',
  slot: 'top',
  price_inr: 12900,
  color: 'Ivory',
  description:
    'The formal bandhgala, cut close through the chest with a banded collar for a distinctly ceremonial finish.',
  brand: 'LOOKLOCK Studio',
  image_url: '/api/v1/catalog/items/upper-ivory-bandhgala/image',
  is_demo: true,
  matches_occasion: true,
  matches_style: true,
  currency: 'INR',
  category: 'Ethnic Wear',
  subcategory: 'Bandhgala',
  colors: ['Ivory', 'Cream'],
  retailer: null,
  purchase_url: null,
  can_shop: false,
  source: null,
  source_product_id: null,
  availability: 'unknown',
  is_tryon_capable: true,
  tryon_uses_remote_image: false,
}

const churidar: ScoredProduct = {
  product_id: 'lower-ivory-churidar',
  name: 'Ivory Churidar',
  slot: 'bottom',
  price_inr: 1500,
  color: 'Ivory',
  description: 'A fitted gathered churidar in ivory, the traditional pairing for a sherwani or bandhgala.',
  brand: 'LOOKLOCK Studio',
  image_url: '/api/v1/catalog/items/lower-ivory-churidar/image',
  is_demo: true,
  matches_occasion: true,
  matches_style: true,
  currency: 'INR',
  category: 'Ethnic Wear',
  subcategory: 'Churidar',
  colors: ['Ivory', 'Cream', 'Gold'],
  retailer: null,
  purchase_url: null,
  can_shop: false,
  source: null,
  source_product_id: null,
  availability: 'unknown',
  is_tryon_capable: true,
  tryon_uses_remote_image: false,
}

const bandhgalaJacket: ScoredProduct = {
  product_id: 'outer-ivory-bandhgala-jacket',
  name: 'Ivory Bandhgala Jacket',
  slot: 'outerwear',
  price_inr: 6800,
  color: 'Ivory',
  description: 'A long brocade bandhgala jacket in ivory, the traditional outer layer worn open over a churidar.',
  brand: 'LOOKLOCK Studio',
  image_url: '/api/v1/catalog/items/outer-ivory-bandhgala-jacket/image',
  is_demo: true,
  matches_occasion: true,
  matches_style: true,
  currency: 'INR',
  category: 'Ethnic Wear',
  subcategory: 'Bandhgala Jacket',
  colors: ['Ivory', 'Champagne'],
  retailer: null,
  purchase_url: null,
  can_shop: false,
  source: null,
  source_product_id: null,
  availability: 'unknown',
  is_tryon_capable: true,
  tryon_uses_remote_image: false,
}

const mojari: ScoredProduct = {
  product_id: 'shoes-cream-mojari',
  name: 'Ivory Mojari',
  slot: 'footwear',
  price_inr: 2900,
  color: 'Ivory',
  description: 'A plain ivory mojari with a light embroidered vamp.',
  brand: 'LOOKLOCK Studio',
  image_url: '/api/v1/catalog/items/shoes-cream-mojari/image',
  is_demo: true,
  matches_occasion: true,
  matches_style: true,
  currency: 'INR',
  category: 'Footwear',
  subcategory: 'Mojari',
  colors: ['Ivory', 'Cream'],
  retailer: null,
  purchase_url: null,
  can_shop: false,
  source: null,
  source_product_id: null,
  availability: 'unknown',
  is_tryon_capable: true,
  tryon_uses_remote_image: false,
}

const pocketSquare: ScoredProduct = {
  product_id: 'accessory-pocket-square',
  name: 'Ivory Pocket Square',
  slot: 'accessory',
  price_inr: 700,
  color: 'Ivory',
  description: 'An ivory pocket square, the detail that finishes a formal jacket.',
  brand: 'LOOKLOCK Studio',
  image_url: '/api/v1/catalog/items/accessory-pocket-square/image',
  is_demo: true,
  matches_occasion: true,
  matches_style: true,
  currency: 'INR',
  category: 'Accessories',
  subcategory: 'Pocket Square',
  colors: ['Ivory', 'Cream', 'White'],
  retailer: null,
  purchase_url: null,
  can_shop: false,
  source: null,
  source_product_id: null,
  availability: 'unknown',
  is_tryon_capable: false,
  tryon_uses_remote_image: false,
}

/** `look-1` of the Wedding / Classic / ₹8,000 response, verbatim. */
export const lookOneFixture: LookRecommendation = {
  look_id: 'look-1',
  rank: 1,
  name: 'Ceremonial Bandhgala',
  total_price_inr: 24800,
  hero_product_id: 'outer-ivory-bandhgala-jacket',
  items: [bandhgala, churidar, bandhgalaJacket, mojari, pocketSquare],
  score: { occasion: 1, style: 1, budget: 0.1452, completeness: 1, total: 0.7863 },
  reasons: [
    'Every piece is styled for wedding',
    'Consistently classic throughout',
    '₹24,800 - ₹16,800 over your budget',
    'Complete look, layered and finished',
  ],
  visual: {
    kind: 'composite',
    image_url: null,
    layers: [
      {
        product_id: 'upper-ivory-bandhgala',
        slot: 'top',
        image_url: '/api/v1/catalog/items/upper-ivory-bandhgala/image',
        alt: 'Ivory Bandhgala in Ivory',
        scale: 0.92,
        x: 0.5,
        vertical: true,
      },
      {
        product_id: 'lower-ivory-churidar',
        slot: 'bottom',
        image_url: '/api/v1/catalog/items/lower-ivory-churidar/image',
        alt: 'Ivory Churidar in Ivory',
        scale: 0.78,
        x: 0.5,
        vertical: true,
      },
      {
        product_id: 'outer-ivory-bandhgala-jacket',
        slot: 'outerwear',
        image_url: '/api/v1/catalog/items/outer-ivory-bandhgala-jacket/image',
        alt: 'Ivory Bandhgala Jacket in Ivory',
        scale: 1,
        x: 0.5,
        vertical: true,
      },
      {
        product_id: 'shoes-cream-mojari',
        slot: 'footwear',
        image_url: '/api/v1/catalog/items/shoes-cream-mojari/image',
        alt: 'Ivory Mojari in Ivory',
        scale: 0.46,
        x: 0.5,
        vertical: false,
      },
      {
        product_id: 'accessory-pocket-square',
        slot: 'accessory',
        image_url: '/api/v1/catalog/items/accessory-pocket-square/image',
        alt: 'Ivory Pocket Square in Ivory',
        scale: 0.26,
        x: 0.78,
        vertical: false,
      },
    ],
    demo_imagery: true,
    alt: 'Ceremonial Bandhgala composed from 5 product images',
  },
}

/**
 * A look whose pieces have real retailer listings, for the shopping paths.
 *
 * Not something the demo catalogue can produce today - it reports
 * `supports_shopping: false` and every `purchase_url` is null - but the UI has
 * to work when a provider is connected, and there is no other way to exercise
 * that code than to give it a response shaped like one.
 */
export const shoppableLookFixture: LookRecommendation = {
  ...lookOneFixture,
  look_id: 'look-shoppable',
  name: 'Ceremonial Sherwani',
  total_price_inr: 7800,
  hero_product_id: 'upper-ivory-sherwani',
  items: [
    {
      ...bandhgala,
      product_id: 'upper-ivory-sherwani',
      name: 'Ivory Silk Sherwani',
      price_inr: 3800,
      subcategory: 'Sherwani',
      retailer: 'Kapoor & Sons',
      purchase_url: 'https://retailer.example.com/p/ivory-silk-sherwani',
      can_shop: true,
      source: 'amazon',
      source_product_id: 'B0SHERWANI1',
      availability: 'in_stock',
      is_demo: false,
      tryon_uses_remote_image: true,
    },
    {
      ...churidar,
      retailer: 'Kapoor & Sons',
      purchase_url: 'https://retailer.example.com/p/ivory-churidar',
      can_shop: true,
      source: 'amazon',
      source_product_id: 'B0CHURIDAR1',
      availability: 'in_stock',
      is_demo: false,
      tryon_uses_remote_image: true,
    },
    {
      ...mojari,
      retailer: 'Rajasthan Crafts',
      purchase_url: 'https://retailer.example.com/p/zari-mojari',
      can_shop: true,
      source: 'amazon',
      source_product_id: 'B0MOJARI001',
      availability: 'out_of_stock',
      is_demo: false,
      tryon_uses_remote_image: true,
    },
    {
      ...pocketSquare,
      retailer: 'Kapoor & Sons',
      purchase_url: 'https://retailer.example.com/p/pocket-square',
      can_shop: true,
      source: 'amazon',
      source_product_id: 'B0POCKET01',
      availability: 'in_stock',
      is_demo: false,
      tryon_uses_remote_image: true,
    },
  ],
  score: { occasion: 1, style: 1, budget: 0.95, completeness: 1, total: 0.88 },
  reasons: ['Every piece is styled for wedding', '₹7,800 of your ₹8,000 budget'],
  visual: {
    kind: 'composite',
    image_url: null,
    layers: [
      {
        product_id: 'upper-ivory-sherwani',
        slot: 'top',
        image_url: '/api/v1/catalog/items/upper-ivory-sherwani/image',
        alt: 'Ivory Silk Sherwani in Ivory',
        scale: 0.92,
        x: 0.5,
        vertical: true,
      },
    ],
    demo_imagery: false,
    alt: 'Ceremonial Sherwani composed from 4 product images',
  },
}

/**
 * `POST /api/v1/recommendations` for Wedding / Classic / ₹8,000, verbatim.
 *
 * Note the notice. This catalogue has no affordable *wedding* wear at all - the
 * cheapest ceremonial outfit is ₹24,200 - so all three looks come back over
 * budget and the engine names the real floor rather than implying the budget was
 * met. That is the case the budget UI most easily gets wrong.
 */
export const weddingOverBudgetFixture: RecommendationResponse = {
  occasion: 'Wedding',
  style: 'Classic',
  budget_inr: 8000,
  looks: [
    lookOneFixture,
    {
      ...lookOneFixture,
      look_id: 'look-2',
      rank: 2,
      name: 'Ceremonial Sherwani',
      total_price_inr: 32800,
      score: { occasion: 1, style: 1, budget: 0.1098, completeness: 1, total: 0.7774 },
    },
    {
      ...lookOneFixture,
      look_id: 'look-3',
      rank: 3,
      name: 'Ceremonial Sherwani with Churidar',
      total_price_inr: 24200,
      score: { occasion: 1, style: 1, budget: 0.1488, completeness: 0.4, total: 0.6972 },
    },
  ],
  notice: 'The most affordable wedding look here is ₹24,200, above the ₹8,000 budget',
  relaxed_constraints: ['budget'],
}

/**
 * Three looks that all fit ₹25,000, with no demo products or imagery.
 *
 * A "met" budget state needs all three looks present, because a short response
 * is reported as a thin catalogue instead - that is deliberate, and the fixture
 * has to respect it to test the affordable path at all.
 */
export const weddingWithinBudgetFixture: RecommendationResponse = {
  occasion: 'Wedding',
  style: 'Classic',
  budget_inr: 25000,
  looks: [
    {
      ...shoppableLookFixture,
      look_id: 'look-1',
      rank: 1,
      total_price_inr: 24800,
      score: { occasion: 1, style: 1, budget: 0.992, completeness: 1, total: 0.94 },
    },
    {
      ...shoppableLookFixture,
      look_id: 'look-2',
      rank: 2,
      name: 'Ivory Sherwani and Churidar',
      total_price_inr: 19800,
      score: { occasion: 1, style: 1, budget: 0.792, completeness: 1, total: 0.92 },
    },
    {
      ...shoppableLookFixture,
      look_id: 'look-3',
      rank: 3,
      name: 'Plain Ivory Sherwani',
      total_price_inr: 16400,
      score: { occasion: 1, style: 1, budget: 0.656, completeness: 0.4, total: 0.9 },
    },
  ],
  notice: null,
  relaxed_constraints: [],
}

/** Vacation / Minimal / ₹2,000: one affordable look, two over. */
export const vacationPartialFixture: RecommendationResponse = {
  occasion: 'Vacation',
  style: 'Minimal',
  budget_inr: 2000,
  looks: [
    {
      ...lookOneFixture,
      look_id: 'look-1',
      name: 'Coastal Shirting',
      total_price_inr: 1600,
      hero_product_id: 'upper-cream-mandarin',
      score: { occasion: 1, style: 1, budget: 0.8, completeness: 0, total: 0.8 },
      visual: { ...lookOneFixture.visual, demo_imagery: true },
    },
    { ...lookOneFixture, look_id: 'look-2', name: 'Coastal Layers', total_price_inr: 13250 },
    { ...lookOneFixture, look_id: 'look-3', name: 'Coastal Skirts', total_price_inr: 9200 },
  ],
  notice: 'Only 1 of these fits ₹2,000, and the others start at ₹9,200',
  relaxed_constraints: ['budget'],
}

/** A look with a real styled photograph, which the demo catalogue never produces. */
export const styledLookFixture: LookRecommendation = {
  ...shoppableLookFixture,
  look_id: 'look-styled',
  name: 'Ivory Wedding Look',
  visual: {
    kind: 'complete_look',
    image_url: '/api/v1/catalog/items/upper-ivory-sherwani/styled',
    layers: [],
    demo_imagery: false,
    alt: 'Ivory Wedding Look, styled by Kapoor & Sons',
  },
}

/** A look the backend could not illustrate, which must fall back to a grid. */
export const gridLookFixture: LookRecommendation = {
  ...lookOneFixture,
  look_id: 'look-grid',
  visual: {
    kind: 'grid',
    image_url: null,
    layers: [],
    demo_imagery: true,
    alt: 'Ceremonial Bandhgala shown as 5 separate products',
  },
}