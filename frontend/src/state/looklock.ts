/**
 * The LOOKLOCK session: what the shopper chose, and what came back.
 *
 * A single context rather than a store library. The whole product loop is one
 * linear journey - occasion, style, budget, photo, three looks - so the state
 * genuinely is one object, and a reducer makes the transitions explicit.
 *
 * This module holds the state shape, the reducer and the `useLookSession` hook.
 * The provider component lives alongside it in `LookSessionProvider.tsx`; the
 * split is so this file exports no component, which is what keeps React Fast
 * Refresh able to hot-reload the provider.
 *
 * Nothing here is persisted. The answers describe the person using the app, the
 * photo is held as an in-memory object URL, and neither belongs in
 * `localStorage` - a refresh losing the session is the intended behaviour, not
 * a bug to work around.
 */

import { createContext, useContext } from 'react'

import type { CatalogueSummary, Occasion, RecommendationResponse, Style } from '@/api/types'

/** Bounds for the custom budget field. Mirrors `app/recommendations/schemas.py`. */
export const MIN_BUDGET_INR = 500
export const MAX_BUDGET_INR = 500000
/** Ceiling behind the open-ended top budget preset. */
export const OPEN_BUDGET_CEILING_INR = 60000

export interface LookAnswers {
  occasion: Occasion | null
  style: Style | null
  budgetInr: number | null
  photo: File | null
  /** Explicit consent to hand the photo to the try-on service. */
  consent: boolean
}

export interface LookSession extends LookAnswers {
  recommendation: RecommendationResponse | null
  catalogue: CatalogueSummary | null
  pending: boolean
  error: string | null
}

export type SessionAction =
  | { type: 'catalogue'; catalogue: CatalogueSummary }
  | { type: 'set'; patch: Partial<LookAnswers> }
  | { type: 'pending' }
  | { type: 'recommended'; recommendation: RecommendationResponse }
  | { type: 'failed'; error: string }
  | { type: 'clear' }

export const initialSession: LookSession = {
  occasion: null,
  style: null,
  budgetInr: null,
  photo: null,
  consent: false,
  recommendation: null,
  catalogue: null,
  pending: false,
  error: null,
}

export function sessionReducer(state: LookSession, action: SessionAction): LookSession {
  switch (action.type) {
    case 'catalogue':
      return { ...state, catalogue: action.catalogue }
    case 'set':
      return { ...state, ...action.patch, error: null }
    case 'pending':
      return { ...state, pending: true, error: null }
    case 'recommended':
      return { ...state, pending: false, recommendation: action.recommendation, error: null }
    case 'failed':
      return { ...state, pending: false, error: action.error }
    case 'clear':
      return initialSession
  }
}

export interface LookSessionValue extends LookSession {
  /** Object URL for `photo`, for local preview only. Never sent anywhere. */
  photoPreviewUrl: string | null
  setAnswers: (patch: Partial<LookAnswers>) => void
  loadCatalogue: (signal?: AbortSignal) => Promise<void>
  buildLooks: (signal?: AbortSignal) => Promise<RecommendationResponse | null>
  reset: () => void
  /** True once occasion, style, budget, photo and consent are all in place. */
  canBuild: boolean
}

export const LookSessionContext = createContext<LookSessionValue | null>(null)

export function useLookSession(): LookSessionValue {
  const value = useContext(LookSessionContext)
  if (!value) {
    throw new Error('useLookSession must be used inside a LookSessionProvider')
  }
  return value
}
