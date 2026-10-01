/**
 * The session provider: the one piece of shared state in the app.
 *
 * Kept in its own file so `looklock.ts` exports no component, which is what lets
 * React Fast Refresh hot-reload this component without a full reload.
 */

import { useCallback, useEffect, useMemo, useReducer, type ReactNode } from 'react'

import { getCatalogueSummary, postRecommendations } from '@/api/looklock'
import type { Occasion, Style } from '@/api/types'
import {
  LookSessionContext,
  initialSession,
  sessionReducer,
  type LookAnswers,
  type LookSessionValue,
} from './looklock'

export function LookSessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(sessionReducer, initialSession)

  const setAnswers = useCallback((patch: Partial<LookAnswers>) => {
    dispatch({ type: 'set', patch })
  }, [])

  const reset = useCallback(() => dispatch({ type: 'clear' }), [])

  // Derived rather than stored: the URL is computable from `photo`, and holding
  // it in state would mean a second render plus a manual revoke on every change.
  const photoPreviewUrl = useMemo(
    () => (state.photo ? URL.createObjectURL(state.photo) : null),
    [state.photo],
  )

  useEffect(() => {
    if (!photoPreviewUrl) return
    return () => URL.revokeObjectURL(photoPreviewUrl)
  }, [photoPreviewUrl])

  const loadCatalogue = useCallback(async (signal?: AbortSignal) => {
    const catalogue = await getCatalogueSummary(signal)
    dispatch({ type: 'catalogue', catalogue })
  }, [])

  const buildLooks = useCallback(
    async (signal?: AbortSignal) => {
      dispatch({ type: 'pending' })
      try {
        const recommendation = await postRecommendations(
          {
            // `canBuild` and the wizard's own guard both ensure these are set
            // before the button that triggers this is enabled.
            occasion: state.occasion as Occasion,
            style: state.style as Style,
            budget_inr: state.budgetInr as number,
          },
          signal,
        )
        dispatch({ type: 'recommended', recommendation })
        return recommendation
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') return null
        dispatch({
          type: 'failed',
          error: cause instanceof Error ? cause.message : 'Could not build your looks.',
        })
        return null
      }
    },
    [state.occasion, state.style, state.budgetInr],
  )

  const value = useMemo<LookSessionValue>(
    () => ({
      ...state,
      photoPreviewUrl,
      setAnswers,
      loadCatalogue,
      buildLooks,
      reset,
      canBuild: Boolean(
        state.occasion && state.style && state.budgetInr && state.photo && state.consent,
      ),
    }),
    [state, photoPreviewUrl, setAnswers, loadCatalogue, buildLooks, reset],
  )

  return <LookSessionContext.Provider value={value}>{children}</LookSessionContext.Provider>
}
