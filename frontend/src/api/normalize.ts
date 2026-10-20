/**
 * Normalisation of backend responses into view models.
 *
 * Everything the UI would otherwise have to derive on its own lives here: the
 * human role label for a slot, whether a product can actually be bought, which
 * budget state a response represents, which garment a look is named after.
 *
 * The point is that a React component never inspects a raw API field to decide
 * something. It asks the view model. That keeps the answer to "is this
 * shoppable?" in one place, so it cannot differ between the look card, the look
 * detail page and the shop page.
 *
 * Nothing here fabricates. A product is shoppable only when the backend said so;
 * a missing retailer is never filled in with a guess.
 */

import type {
  Availability,
  CatalogueSummary,
  LookRecommendation,
  Product,
  RecommendationResponse,
  ScoredProduct,
} from './types'
import { slotLabel, slotRank } from '@/lib/format'

/**
 * Readable role for each slot. Derived from `slot` alone, never from a name.
 *
 * The slot vocabulary and its display order live in `lib/format`; this module is
 * the only place that decides what a *response* means, so it borrows the labels
 * rather than keeping a second copy that could drift.
 */

/** Sort helper: places a look's items in dressing order, unknowns last. */
export function byDressingOrder(a: ScoredProduct, b: ScoredProduct): number {
  return slotRank(a.slot) - slotRank(b.slot)
}

/** Readable role for a product, from its backend `slot`. */
export function roleLabel(slot: string): string {
  return slotLabel(slot)
}

/** A product prepared for display, with every purchase-related decision made. */
export interface ProductView {
  item: ScoredProduct
  /** `Top`, `Outerwear`, ... from the backend's slot. */
  role: string
  price: string
  /**
   * The URL to link to, or `null` when there is nothing verified to link to.
   *
   * Gated on `can_shop` rather than on the mere presence of `purchase_url`, so a
   * half-populated provider record can never produce a button that goes nowhere.
   */
  shopUrl: string | null
  /** Retailer to name in "Shop at X". `null` when unknown. */
  retailerName: string | null
  /** Whether this item's imagery is illustrative rather than a real listing photo. */
  isDemo: boolean
  /** Whether the try-on service can accept this garment as its reference. */
  tryonCapable: boolean
  /**
   * Whether try-on can actually run for this piece right now.
   *
   * Same as `tryonCapable` except for a piece whose only reference is a remote
   * image the engine has to fetch: the vendor cannot accept those yet, so the
   * button stays disabled rather than starting a job that would fail.
   */
  tryonReady: boolean
  /** Whether the try-on reference is a remote/CDN image, for the explanatory note. */
  tryonRemoteImage: boolean
  /**
   * Whether this listing is buyable right now.
   *
   * `shopUrl` deliberately ignores this: a verified URL is still the correct link
   * to show for a sold-out item, because that is the page a shopper needs in order
   * to check or wait for restock. Suppressing the link would be hiding the answer.
   */
  availability: Availability
  productLinkType?: 'direct_retailer' | 'google_shopping' | null
}

/** Label for a listing's stock state, or `null` when the source did not say. */
export function availabilityLabel(availability: Availability): string | null {
  if (availability === 'out_of_stock') return 'Out of stock'
  return null
}

/** A product as listed in the catalogue, for shop and browse surfaces. */
export interface CatalogueProductView {
  product: Product
  role: string
  price: string
  shopUrl: string | null
  retailerName: string | null
  isDemo: boolean
  availability: Availability
  productLinkType?: 'direct_retailer' | 'google_shopping' | null
}

export function toProductView(item: ScoredProduct, formatPrice: (n: number) => string): ProductView {
  const tryonRemoteImage = item.tryon_uses_remote_image
  return {
    item,
    role: roleLabel(item.slot),
    price: formatPrice(item.price_inr),
    shopUrl: item.can_shop ? (item.purchase_url ?? null) : null,
    retailerName: item.retailer,
    isDemo: item.is_demo,
    tryonCapable: item.is_tryon_capable,
    tryonReady: item.is_tryon_capable && !tryonRemoteImage,
    tryonRemoteImage,
    availability: item.availability,
    productLinkType: (item as any).product_link_type ?? null,
  }
}

/**
 * A look's items as display views, in dressing order.
 *
 * Used by every surface that lists a look's pieces, so the look detail page and
 * the shop page cannot disagree about what a garment is called or whether it is
 * buyable.
 */
export function toProductViews(
  items: readonly ScoredProduct[],
  formatPrice: (n: number) => string,
): ProductView[] {
  return [...items].sort(byDressingOrder).map((item) => toProductView(item, formatPrice))
}

export function toCatalogueProductView(
  product: Product,
  formatPrice: (n: number) => string,
): CatalogueProductView {
  return {
    product,
    role: roleLabel(product.slot),
    price: formatPrice(product.price_inr),
    shopUrl: product.can_shop ? (product.purchase_url ?? null) : null,
    retailerName: product.retailer,
    isDemo: product.is_demo,
    availability: product.availability,
    productLinkType: (product as any).product_link_type ?? null,
  }
}

/**
 * Which of the four budget situations a response represents.
 *
 * The backend distinguishes these carefully - in particular between "the
 * catalogue is too small" and "nothing affordable is appropriate here" - and the
 * difference changes what the shopper should be told, so it is preserved rather
 * than flattened into a boolean.
 */
export type BudgetStatus =
  /** Every returned look is within the shopper's budget. */
  | 'met'
  /** Some looks fit, some do not. The affordable ones are listed first. */
  | 'partial'
  /** Nothing appropriate for this occasion fits the budget. */
  | 'none_affordable'
  /** The catalogue could not produce three looks at all. */
  | 'thin_catalogue'

export interface BudgetView {
  status: BudgetStatus
  budgetInr: number
  /** Formats a price for the shopper-facing strings above. */
  overBudgetCount: number
  inBudgetCount: number
  /** True when the response carries the backend's own explanation. */
  hasNotice: boolean
  notice: string | null
  relaxed: string[]
}

export function toBudgetView(
  response: Pick<RecommendationResponse, 'budget_inr' | 'looks' | 'notice' | 'relaxed_constraints'>,
): BudgetView {
  const overBudgetCount = response.looks.filter(
    (look) => look.total_price_inr > response.budget_inr,
  ).length
  const inBudgetCount = response.looks.length - overBudgetCount

  let status: BudgetStatus
  if (response.looks.length < 3) {
    status = 'thin_catalogue'
  } else if (inBudgetCount === 0) {
    status = 'none_affordable'
  } else if (overBudgetCount === 0) {
    status = 'met'
  } else {
    status = 'partial'
  }

  return {
    status,
    budgetInr: response.budget_inr,
    overBudgetCount,
    inBudgetCount,
    hasNotice: Boolean(response.notice),
    notice: response.notice,
    relaxed: [...response.relaxed_constraints],
  }
}

/**
 * The garment a look is named after, found by looking for the piece whose
 * `subcategory` the backend's own look name mentions.
 *
 * This reads the normalised `subcategory` field and only cross-references it
 * against copy the backend wrote - it never guesses a category from a product
 * name. Returns `null` when the name mentions no known subcategory, so callers
 * can fall back to a plain piece count.
 */
export function signatureItem(look: LookRecommendation): ScoredProduct | null {
  const haystack = look.name.toLowerCase()
  const match = look.items.find((item) => {
    const subcategory = item.subcategory?.toLowerCase()
    return Boolean(subcategory) && haystack.includes(subcategory as string)
  })
  if (match) return match
  // No overlap: fall back to the hero, which is the item the try-on will use and
  // therefore the one the shopper is about to identify this look with.
  return look.items.find((item) => item.product_id === look.hero_product_id) ?? look.items[0] ?? null
}

/** A recommended look prepared for display. */
export interface LookView {
  look: LookRecommendation
  /** Backend-authored name, e.g. "Ceremonial Sherwani". */
  name: string
  /** e.g. "Sherwani + 3 more pieces". */
  summary: string
  /** Item count in the look. */
  pieceCount: number
  price: string
  /** Whole percentage, e.g. 79. */
  matchPercent: number
  /** Backend `kind`, which drives the visual renderer. */
  visualKind: LookRecommendation['visual']['kind']
  demoImagery: boolean
  /** Alt text for the look visual, from the backend. */
  visualAlt: string
  items: ScoredProduct[]
  /** Items in dressing order, for the breakdown list. */
  orderedItems: ScoredProduct[]
  /** The same items as display views, in dressing order. */
  productViews: ProductView[]
  /** The try-on reference garment. */
  hero: ScoredProduct | null
  heroView: ProductView | null
  overBudget: boolean
  /** How far over, in rupees. Zero when within budget. */
  overByInr: number
  budgetInr: number
  /** Products with a verified retailer link. */
  shoppableItems: ProductView[]
  /** True only when every single piece can actually be bought. */
  isShoppable: boolean
  /** Distinct retailers behind this look, in item order. */
  retailerNames: string[]
  /** Whether any imagery in this look is illustrative. */
  hasDemoImagery: boolean
}

export function toLookView(
  look: LookRecommendation,
  budgetInr: number,
  formatPrice: (n: number) => string,
): LookView {
  const orderedItems = [...look.items].sort(byDressingOrder)
  const productViews = toProductViews(look.items, formatPrice)
  const hero = look.items.find((item) => item.product_id === look.hero_product_id) ?? null
  const shoppableItems = productViews.filter((view) => view.shopUrl !== null)

  const retailerNames: string[] = []
  for (const item of orderedItems) {
    if (item.retailer && !retailerNames.includes(item.retailer)) retailerNames.push(item.retailer)
  }

  const overByInr = Math.max(0, look.total_price_inr - budgetInr)

  return {
    look,
    name: look.name,
    summary: lookSummary(look),
    pieceCount: look.items.length,
    price: formatPrice(look.total_price_inr),
    matchPercent: Math.round(look.score.total * 100),
    visualKind: look.visual.kind,
    demoImagery: look.visual.demo_imagery,
    visualAlt: look.visual.alt,
    items: look.items,
    orderedItems,
    productViews,
    hero,
    heroView: hero ? toProductView(hero, formatPrice) : null,
    overBudget: overByInr > 0,
    overByInr,
    budgetInr,
    shoppableItems,
    isShoppable: productViews.length > 0 && shoppableItems.length === productViews.length,
    retailerNames,
    hasDemoImagery: look.visual.demo_imagery || look.items.some((item) => item.is_demo),
  }
}

/**
 * One line naming the outfit rather than its first product: "Sherwani + 3 more
 * pieces". Reads the signature garment out of the backend's look name rather
 * than reaching for `items[0]`, which is how a five-piece outfit ends up
 * captioned with a shirt.
 */
function lookSummary(look: LookRecommendation): string {
  const signature = signatureItem(look)
  const noun = signature?.subcategory?.trim()
  const extra = look.items.length - 1

  if (extra <= 0) return noun || '1 piece'
  const remainder = extra === 1 ? '1 more piece' : `${extra} more pieces`
  return noun ? `${noun} + ${remainder}` : `${look.items.length} pieces`
}

/** The full recommendation response prepared for display. */
export interface RecommendationView {
  response: RecommendationResponse
  occasion: string
  style: string
  budgetInr: number
  budget: BudgetView
  looks: LookView[]
  /** True when any look uses illustrative rather than real photography. */
  hasDemoImagery: boolean
  /** How many looks came back. Three is the intended number. */
  lookCount: number
}

export function toRecommendationView(
  response: RecommendationResponse,
  formatPrice: (n: number) => string,
): RecommendationView {
  const budget = toBudgetView(response)
  return {
    response,
    occasion: response.occasion,
    style: response.style,
    budgetInr: response.budget_inr,
    budget,
    looks: response.looks.map((look) => toLookView(look, response.budget_inr, formatPrice)),
    hasDemoImagery: response.looks.some(
      (look) => look.visual.demo_imagery || look.items.some((item) => item.is_demo),
    ),
    lookCount: response.looks.length,
  }
}

/** Catalogue summary with the provider's capabilities unpacked for the UI. */
export interface CatalogueView {
  summary: CatalogueSummary
  productCount: number
  occasions: CatalogueSummary['occasions']
  styles: CatalogueSummary['styles']
  budgetPresets: number[]
  /** Whether any provider can produce verified buy links. */
  supportsShopping: boolean
  /** Whether the imagery is illustrative. Drives the demo treatment. */
  demoImagery: boolean
  /** The backend's own explanation, shown verbatim. */
  notice: string
  providerName: string
  /**
   * Whether a live catalogue could be served at all.
   *
   * Kept apart from `supportsShopping`: a provider can be capable and still be
   * down or unconfigured, and the shopper needs "Amazon is unreachable" rather
   * than a demo notice implying they are seeing sample data.
   */
  providerAvailable: boolean
  /** Why no live catalogue could be served. `null` while `providerAvailable`. */
  providerUnavailableReason: string | null
}

export function toCatalogueView(summary: CatalogueSummary): CatalogueView {
  return {
    summary,
    productCount: summary.product_count,
    occasions: summary.occasions,
    styles: summary.styles,
    budgetPresets: summary.budget_presets_inr,
    supportsShopping: summary.supports_shopping,
    demoImagery: summary.demo_imagery,
    notice: summary.notice,
    providerName: summary.provider_name,
    providerAvailable: summary.provider_available,
    providerUnavailableReason: summary.provider_unavailable_reason,
  }
}
