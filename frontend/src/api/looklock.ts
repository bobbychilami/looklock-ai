/**
 * Backend endpoints used by the app.
 *
 * Every function returns a view model rather than a raw wire shape, so the
 * response-shape conversions live in one file (`normalize.ts`) and the React
 * components never branch on an API field. Nothing here calls `fetch` directly.
 */

import { apiGet, apiPostForm, apiPostJson } from './client'
import { toCatalogueView, toProductView, toRecommendationView } from './normalize'
import type { CatalogueView, LookView, ProductView, RecommendationView } from './normalize'
import { formatInr } from '@/lib/format'
import type {
  CatalogueSummary,
  HealthResponse,
  IntegrationStatusResponse,
  Product,
  ProductTryOnAcceptedResponse,
  ProductTryOnStatusResponse,
  ReadyResponse,
  RecommendationRequest,
  RecommendationResponse,
  TryOnAcceptedResponse,
  TryOnOptionsResponse,
  TryOnStatusResponse,
} from './types'

export function getHealth(signal?: AbortSignal) {
  return apiGet<HealthResponse>('/health', signal)
}

export function getReadiness(signal?: AbortSignal) {
  return apiGet<ReadyResponse>('/ready', signal)
}

export function getIntegrationStatus(signal?: AbortSignal) {
  return apiGet<IntegrationStatusResponse>('/integration/ycam/status', signal)
}

export function getTryOnOptions(signal?: AbortSignal) {
  return apiGet<TryOnOptionsResponse>('/integration/ycam/vto/options', signal)
}

/**
 * Start one AI Clothes Virtual Try-On V4.0 proof of concept.
 *
 * Returns as soon as the images are accepted; the vendor work continues in the
 * background, so poll `getTryOnJob` with the returned `job_id`.
 */
export function startTryOn(
  form: FormData,
  signal?: AbortSignal,
): Promise<TryOnAcceptedResponse> {
  return apiPostForm<TryOnAcceptedResponse>('/integration/ycam/vto/test', form, signal)
}

export function getTryOnJob(jobId: string, signal?: AbortSignal) {
  return apiGet<TryOnStatusResponse>(`/integration/ycam/vto/test/${encodeURIComponent(jobId)}`, signal)
}

/**
 * Catalogue vocabulary, provider capabilities and shape.
 *
 * Fetched rather than hard-coded so the onboarding options can never drift from
 * what the request schema accepts, and so the UI learns whether this deployment
 * can produce real retailer links instead of assuming it cannot.
 */
export async function getCatalogueSummary(signal?: AbortSignal): Promise<CatalogueView> {
  return toCatalogueView(await apiGet<CatalogueSummary>('/catalog/looks', signal))
}

export async function getProduct(
  productId: string,
  signal?: AbortSignal,
): Promise<ProductView | null> {
  const product = await apiGet<Product>(`/catalog/items/${encodeURIComponent(productId)}`, signal)
  return toProductView(toScoredShape(product), formatInr)
}

/**
 * Rank the catalogue against the shopper's answers.
 *
 * Pure and deterministic server-side: the same answers always produce the same
 * looks in the same order, so no client-side shuffling is needed. Budget state,
 * look names and shoppability are all resolved here rather than in the
 * components that render them.
 */
export async function postRecommendations(
  request: RecommendationRequest,
  signal?: AbortSignal,
): Promise<RecommendationView> {
  const response = await apiPostJson<RecommendationResponse>('/recommendations', request, signal)
  return toRecommendationView(response, formatInr)
}

/** Look up one prepared look inside an already-fetched recommendation. */
export function findLookView(view: RecommendationView, lookId: string): LookView | undefined {
  return view.looks.find((candidate) => candidate.look.look_id === lookId)
}

/**
 * Try one catalogue garment on the shopper's photo.
 *
 * `product_id` is resolved server-side and the bundled artwork is uploaded
 * through the vendor's own File API, so the browser only ever sends the photo.
 * Returns immediately; poll `getProductTryOnJob` with the returned `job_id`.
 */
export function startProductTryOn(
  productId: string,
  photo: File,
  signal?: AbortSignal,
): Promise<ProductTryOnAcceptedResponse> {
  const form = new FormData()
  form.append('source_image', photo)
  form.append('product_id', productId)
  return apiPostForm<ProductTryOnAcceptedResponse>('/tryon', form, signal)
}

export function getProductTryOnJob(jobId: string, signal?: AbortSignal) {
  return apiGet<ProductTryOnStatusResponse>(`/tryon/${encodeURIComponent(jobId)}`, signal)
}

/**
 * Catalogue products carry `styles[]`/`occasions[]` where a product inside a look
 * carries two match booleans. Reuse the in-look view for a standalone product by
 * supplying neutral match flags - nothing on the shop surface depends on them.
 */
function toScoredShape(product: Product) {
  return {
    ...product,
    matches_occasion: false,
    matches_style: false,
  }
}
