/**
 * Runtime configuration for the browser app.
 *
 * Only VITE_* values are available here, and VITE_* values are PUBLIC: they are
 * inlined into the bundle. That is why no credential is ever read in this file.
 * The browser never talks to YouCam directly - only to our own backend.
 */

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

export const config = {
  /**
   * Empty string means "same origin", which is what the Vite dev proxy and a
   * production reverse proxy both expect.
   */
  apiBaseUrl: rawBaseUrl ? rawBaseUrl.replace(/\/+$/, '') : '',
  apiPrefix: '/api/v1',
} as const

export type AppConfig = typeof config

/**
 * Resolve a URL the backend handed us for display.
 *
 * The catalogue deliberately returns root-relative image paths such as
 * `/api/v1/catalog/items/top-01/image` so no host is baked into stored data:
 * the Vite dev proxy and a production reverse proxy both serve the API from the
 * same origin. The moment `VITE_API_BASE_URL` points somewhere else - a deployed
 * backend, or a phone hitting a laptop on the LAN - those paths stop resolving,
 * so they have to be re-based here. Same-origin relative paths pass through
 * untouched.
 */
export function assetUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined
  if (/^(?:https?:)?\/\//.test(path) || path.startsWith('data:')) return path
  if (!config.apiBaseUrl) return path
  return `${config.apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`
}
