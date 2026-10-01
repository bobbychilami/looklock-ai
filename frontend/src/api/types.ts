/**
 * Typed shapes returned by the LOOKLOCK AI backend.
 *
 * These mirror the FastAPI response models. Keep them in sync with
 * `backend/app/api/routes/`.
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
 * Occasion axis. These literals are owned by the backend
 * (`app/catalog/product.py`) and the onboarding UI must not offer anything the
 * request schema would reject, so they are kept as a union rather than
 * `string[]`.
 */
export type Occasion = 'Wedding' | 'Date Night' | 'Interview' | 'Party' | 'Casual'

/** Style axis. Owned by the backend for the same reason as `Occasion`. */
export type Style = 'Classic' | 'Modern' | 'Bold' | 'Minimal'

/**
 * Where a garment sits in an outfit.
 *
 * `top` and `bottom` are required to build a look; `footwear` and `accessory`
 * are optional. `accessory` is display-only and is never sent to the try-on
 * endpoint.
 */
export type Slot = 'top' | 'bottom' | 'footwear' | 'accessory'

/** Catalogue shape plus the answer vocabulary the onboarding screen renders. */
export interface CatalogueSummary {
  product_count: number
  counts_by_slot: Record<string, number>
  occasions: Occasion[]
  styles: Style[]
  budget_presets_inr: number[]
  is_demo_catalogue: boolean
  notice: string
}

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
}

export interface CatalogueResponse {
  products: Product[]
  summary: CatalogueSummary
}

/** One product as it appears inside a recommended look. */
export interface ScoredProduct extends Product {
  /** Whether this item was chosen because it fits the requested occasion. */
  matches_occasion: boolean
  /** Whether this item was chosen because it fits the requested style. */
  matches_style: boolean
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
  total_price_inr: number
  /** The item the try-on request uses as its reference garment. */
  hero_product_id: string
  items: ScoredProduct[]
  score: LookScore
  reasons: string[]
}

export interface RecommendationResponse {
  occasion: Occasion
  style: Style
  budget_inr: number
  looks: LookRecommendation[]
  /** Set when the catalogue could not fully satisfy the request. */
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
