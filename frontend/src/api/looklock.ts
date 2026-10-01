/** Backend endpoints used by the app. */

import { apiGet, apiPostForm, apiPostJson } from './client'
import type {
  CatalogueResponse,
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
 * Catalogue vocabulary and shape. Fetched rather than hard-coded so the
 * onboarding options can never drift from what the request schema accepts.
 */
export function getCatalogueSummary(signal?: AbortSignal) {
  return apiGet<CatalogueSummary>('/catalog/looks', signal)
}

export function getCatalogue(signal?: AbortSignal) {
  return apiGet<CatalogueResponse>('/catalog/items', signal)
}

export function getProduct(productId: string, signal?: AbortSignal) {
  return apiGet<Product>(`/catalog/items/${encodeURIComponent(productId)}`, signal)
}

/**
 * Rank the catalogue against the shopper's answers.
 *
 * Pure and deterministic server-side: the same answers always produce the same
 * three looks in the same order, so no client-side shuffling is needed.
 */
export function postRecommendations(
  request: RecommendationRequest,
  signal?: AbortSignal,
) {
  return apiPostJson<RecommendationResponse>('/recommendations', request, signal)
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