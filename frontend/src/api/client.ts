/**
 * Minimal fetch wrapper for the LOOKLOCK AI backend.
 *
 * Responsibilities kept deliberately small: build the URL, attach JSON, and
 * turn any failure into an `ApiError` with a message the UI can show. No state
 * management, no retries - callers decide that.
 */

import { config } from '@/config/env'
import type { ApiError } from './types'

export class ApiRequestError extends Error implements ApiError {
  /** Same as the message, kept for callers that destructure the API shape. */
  readonly detail: string
  readonly status: number
  readonly errorCode: string | undefined

  constructor({ detail, errorCode, status }: ApiError) {
    super(detail)
    this.name = 'ApiRequestError'
    this.detail = detail
    this.status = status
    this.errorCode = errorCode
  }
}

function buildUrl(path: string): string {
  const normalised = path.startsWith('/') ? path : `/${path}`
  return `${config.apiBaseUrl}${config.apiPrefix}${normalised}`
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response

  try {
    response = await fetch(buildUrl(path), {
      method: 'GET',
      headers: { Accept: 'application/json' },
      ...(signal ? { signal } : {}),
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw cause
    }
    throw new ApiRequestError({
      detail: 'Could not reach the LOOKLOCK AI backend. Is it running?',
      status: 0,
    })
  }

  if (!response.ok) {
    throw new ApiRequestError(await toApiError(response))
  }

  return (await response.json()) as T
}

/**
 * POST a `FormData` body.
 *
 * `Content-Type` is deliberately left unset: the browser has to add the
 * multipart boundary itself, and setting the header by hand produces a body the
 * server cannot parse.
 */
export async function apiPostForm<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  let response: Response

  try {
    response = await fetch(buildUrl(path), {
      method: 'POST',
      body: form,
      headers: { Accept: 'application/json' },
      ...(signal ? { signal } : {}),
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw cause
    }
    throw new ApiRequestError({
      detail: 'Could not reach the LOOKLOCK AI backend. Is it running?',
      status: 0,
    })
  }

  if (!response.ok) {
    throw new ApiRequestError(await toApiError(response))
  }

  return (await response.json()) as T
}

/**
 * POST a JSON body.
 *
 * The recommendation request is a plain typed object, so it is serialised here
 * rather than by every caller.
 */
export async function apiPostJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response

  try {
    response = await fetch(buildUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      ...(signal ? { signal } : {}),
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw cause
    }
    throw new ApiRequestError({
      detail: 'Could not reach the LOOKLOCK AI backend. Is it running?',
      status: 0,
    })
  }

  if (!response.ok) {
    throw new ApiRequestError(await toApiError(response))
  }

  return (await response.json()) as T
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { detail?: unknown; error_code?: unknown }
    const detail = typeof body.detail === 'string' ? body.detail : response.statusText
    const errorCode = typeof body.error_code === 'string' ? body.error_code : undefined
    return { detail, errorCode, status: response.status }
  } catch {
    return { detail: response.statusText, status: response.status }
  }
}
