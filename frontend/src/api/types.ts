/**
 * Typed shapes returned by the LOOKLOCK AI backend.
 *
 * These mirror the FastAPI response models field for field. They were written
 * from the actual JSON the API emits (captured from a running app), not from
 * assumptions about what the models probably look like - `backend/app/api/routes/`,
 * `backend/app/recommendations/schemas.py` and `backend/app/recommendations/naming.py`
 * are the sources of truth.
 *
 * Two shapes here differ from the pre-provider API and are easy to get wrong:
 *
 * - `ScoredProduct` does NOT extend `Product`. A catalogue product carries
 *   `styles[]` and `occasions[]`; inside a look those arrays are gone and are
 *   replaced by two booleans, `matches_occasion` and `matches_style`, because the
 *   only question that matters there is whether *this* item matched *this* request.
 * - The backend exposes `hero`, `is_shoppable`, `shoppable_items` and
 *   `retailer_names` as plain Python `@property`, which Pydantic does not
 *   serialise. They are therefore absent from the wire format and are derived
 *   here instead, in `api/normalize.ts`.
 */

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
  youcam_configured: boolean
}

export interface ReadyResponse {
  status: string
  youcam_configured: boolean
  detail: string
}

export interface YouCamFeatureStatus {
  name: string
  youcam_endpoint: string
  implemented: boolean
  notes: string
}

export interface IntegrationStatusResponse {
  configured: boolean
  api_base_url: string
  documentation: string
  features: YouCamFeatureStatus[]
  open_items: string[]
}

/** Normalised error the UI can render without inspecting HTTP internals. */
export interface ApiError {
  detail: string
  errorCode?: string
  status: number
}

/**
 * Occasion axis. Owned by the backend (`app/catalog/product.py`) and kept as a
 * union rather than `string[]` so the onboarding UI cannot offer an answer the
 * request schema would reject. `Vacation` was added with the provider work.
 */
export type Occasion = 'Wedding' | 'Date Night' | 'Interview' | 'Party' | 'Casual' | 'Vacation'

/** Style axis. Owned by the backend for the same reason as `Occasion`. */
export type Style = 'Classic' | 'Modern' | 'Bold' | 'Minimal'

/**
 * Where a garment sits in an outfit.
 *
 * `top` and `bottom` are required to build a look. `outerwear` is worn - it is
 * priced, scored and counted towards completeness - and it takes visual priority
 * over the top when choosing the try-on reference. `accessory` is display-only
 * and is never sent to the try-on endpoint.
 */
export type Slot = 'top' | 'bottom' | 'outerwear' | 'footwear' | 'accessory'

/**
 * How a look should be pictured.
 *
 * - `complete_look`: the provider supplied a real styled photograph of the outfit.
 *   `image_url` is set.
 * - `composite`: no styled shot exists, so the picture is assembled on the client
 *   from the look's own real product images, positioned by `layers`.
 * - `grid`: nothing usable; the UI falls back to a plain product grid.
 *
 * LOOKLOCK never generates an image of an outfit. A fabricated picture of the
 * thing someone is about to buy would be indistinguishable in the UI from a real
 * retailer's photograph, which is why the composite path is built out of actual
 * product images instead.
 */
export type VisualKind = 'complete_look' | 'composite' | 'grid'

/** Catalogue shape plus the answer vocabulary the onboarding screen renders. */
export interface CatalogueSummary {
  product_count: number
  counts_by_slot: Record<string, number>
  occasions: Occasion[]
  styles: Style[]
  budget_presets_inr: number[]
  is_demo_catalogue: boolean
  /** Explains, in the backend's own words, why this catalogue cannot be bought. */
  notice: string
  /** Id of the provider or composite that served this response. */
  provider_id: string
  provider_name: string
  /** Whether any provider behind this response can produce verified buy links. */
  supports_shopping: boolean
  /** Whether the imagery on screen is illustrative rather than real photography. */
  demo_imagery: boolean
  /**
   * Whether the provider behind this response could actually answer.
   *
   * Distinct from `supports_shopping`: a provider can be perfectly capable of
   * producing buy links and still be unreachable right now, in which case the
   * shopper is looking at an empty catalogue and needs to be told why.
   */
  provider_available: boolean
  /** Why no live catalogue could be served. `null` while `provider_available`. */
  provider_unavailable_reason: string | null
}

/**
 * Whether a listing can be bought right now.
 *
 * `unknown` is a real answer, not a placeholder for `in_stock`: a marketplace that
 * does not report availability must not be shown as though it confirmed stock, so
 * the UI says nothing rather than implying a guarantee.
 */
export type Availability = 'in_stock' | 'out_of_stock' | 'unknown'

/**
 * A product as the catalogue lists it.
 *
 * `retailer` and `purchase_url` are independent: a provider can know who sells an
 * item without having a URL it is willing to send shoppers to. `can_shop` is the
 * backend's own "both, or neither" answer and is the only thing the UI should
 * branch on - never on the presence of a URL alone.
 */
export interface Product {
  product_id: string
  name: string
  slot: Slot
  price_inr: number
  color: string
  description: string
  styles: Style[]
  occasions: Occasion[]
  brand: string | null
  image_url: string
  purchase_url: string | null
  is_demo: boolean
  is_tryon_capable: boolean
  /**
   * True when the try-on reference is a remote/CDN image the engine must fetch.
   *
   * The try-on service cannot accept those yet, so the UI keeps try-on disabled
   * for the piece and says why rather than starting a job that would fail.
   */
  tryon_uses_remote_image: boolean
  currency: string
  category: string | null
  subcategory: string | null
  colors: string[]
  retailer: string | null
  can_shop: boolean
  /** Which provider supplied this item, e.g. `amazon`. `null` for demo data. */
  source: string | null
  /** The provider's own id for the listing (an ASIN), for tracing a complaint. */
  source_product_id: string | null
  availability: Availability
  product_link_type?: 'direct_retailer' | 'google_shopping' | null
}

export interface CatalogueResponse {
  products: Product[]
  summary: CatalogueSummary
}

/**
 * One product as it appears inside a recommended look.
 *
 * Deliberately not `Product`: inside a look the `styles[]`/`occasions[]` arrays
 * are replaced by the two per-request match booleans.
 */
export interface ScoredProduct {
  product_id: string
  name: string
  slot: Slot
  price_inr: number
  color: string
  description: string
  brand: string | null
  image_url: string
  is_demo: boolean
  /** Whether this item was chosen because it fits the requested occasion. */
  matches_occasion: boolean
  /** Whether this item was chosen because it fits the requested style. */
  matches_style: boolean
  currency: string
  category: string | null
  subcategory: string | null
  colors: string[]
  retailer: string | null
  purchase_url: string | null
  /** Both a real URL and a real retailer, or neither. */
  can_shop: boolean
  /** Accessories complete a look but cannot be sent to the try-on service. */
  is_tryon_capable: boolean
  /**
   * True when the try-on reference is a remote/CDN image the engine must fetch.
   *
   * The try-on service cannot accept those yet, so the UI keeps try-on disabled
   * for the piece and says why rather than starting a job that would fail.
   */
  tryon_uses_remote_image: boolean
  /** Which provider supplied this item, e.g. `amazon`. `null` for demo data. */
  source: string | null
  /** The provider's own id for the listing (an ASIN), for tracing a complaint. */
  source_product_id: string | null
  /**
   * Whether the listing is buyable right now.
   *
   * Carried into every look because an item can satisfy every style and budget
   * rule and still be sold out, and a "Shop this" button that leads to a dead
   * page is worse than an honest label.
   */
  availability: Availability
  product_link_type?: 'direct_retailer' | 'google_shopping' | null
}

/** One garment's image and its place in a `composite` look visual. */
export interface VisualLayer {
  product_id: string
  slot: Slot
  image_url: string
  alt: string
  /** 0..1, larger is a bigger presence in the frame. */
  scale: number
  /** Horizontal anchor within the composition box, 0..1. */
  x: number
  /** Whether this garment is drawn standing rather than laid flat. */
  vertical: boolean
}

/** How to picture a look, as decided server-side. See `VisualKind`. */
export interface LookVisual {
  kind: VisualKind
  /** Only populated for `complete_look`. */
  image_url: string | null
  layers: VisualLayer[]
  /** Whether this imagery is illustrative rather than a real listing photo. */
  demo_imagery: boolean
  /** Describes the visual in words, for `alt`/`aria-label` and captions. */
  alt: string
}

/**
 * The score breakdown behind a look's rank, so the UI can justify the order
 * instead of presenting it as magic. Every component is 0..1.
 */
export interface LookScore {
  occasion: number
  style: number
  budget: number
  completeness: number
  total: number
}

export interface LookRecommendation {
  look_id: string
  rank: number
  /**
   * Editorial name derived from the look's own defining garment, e.g.
   * "Ceremonial Sherwani". Unique across a response and never derived from the
   * first product in the list - a look is an outfit, not a shirt with extras.
   */
  name: string
  total_price_inr: number
  /** The item the try-on request uses as its reference garment. */
  hero_product_id: string
  items: ScoredProduct[]
  score: LookScore
  /** Short phrases naming the attributes that earned the rank. */
  reasons: string[]
  visual: LookVisual
}

export interface RecommendationResponse {
  occasion: Occasion
  style: Style
  budget_inr: number
  looks: LookRecommendation[]
  /**
   * Set when the catalogue could not fully satisfy the request. Written by the
   * engine in shopper-facing language and shown verbatim - replacing it with
   * generic UI copy would hide exactly the thing the shopper needs to know.
   */
  notice: string | null
  relaxed_constraints: string[]
}

export interface RecommendationRequest {
  occasion: Occasion
  style: Style
  budget_inr: number
}

export interface ProductTryOnAcceptedResponse {
  job_id: string
  phase: string
  product_id: string
  product_name: string
  poll_url: string
}

export interface ProductTryOnStatusResponse {
  job_id: string
  phase: TryOnPhase
  product_id: string | null
  product_name: string | null
  filter_multi_person: string
  youcam_task_id: string | null
  youcam_task_status: string | null
  result_url: string | null
  result_url_expires_in_hours: number
  error: string | null
  error_code: string | null
  poll_url: string
  notes: string[]
}

/**
 * Progress of one virtual try-on request.
 *
 * Mirrors the backend's `TryOnPhase`. The order is meaningful: the UI renders a
 * step list from it, so a phase may only ever advance forward.
 */
export type TryOnPhase =
  | 'queued'
  | 'uploading_source_image'
  | 'uploading_reference_image'
  | 'submitting_task'
  | 'polling_task'
  | 'completed'
  | 'failed'

export interface TryOnOptionsResponse {
  youcam_endpoint: string
  garment_categories: string[]
  multi_person_filters: string[]
  documentation: string
  max_image_bytes: number
  phases: TryOnPhase[]
  notes: string[]
}

export interface TryOnAcceptedResponse {
  job_id: string
  phase: string
  poll_url: string
}

export interface TryOnStatusResponse {
  job_id: string
  phase: TryOnPhase
  garment_category: string
  filter_multi_person: string
  youcam_task_id: string | null
  youcam_task_status: string | null
  result_url: string | null
  result_url_expires_in_hours: number
  error: string | null
  error_code: string | null
  poll_url: string
  notes: string[]
}
