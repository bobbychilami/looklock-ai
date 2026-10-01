/**
 * "Your Looks": the three ranked outfits.
 *
 * The notice and the relaxed-constraint list are shown before the looks, not
 * buried underneath. If the catalogue could not fully honour the budget, that is
 * the most important thing on this page.
 */

import { Navigate } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { LookCard } from '@/components/product/LookCard'
import { Button } from '@/components/ui/Button'
import { formatInr } from '@/lib/format'
import { useLookSession } from '@/state/looklock'

export default function Looks() {
  const { style, budgetInr, recommendation, reset } = useLookSession()

  // Arriving without a recommendation means the session was lost, so send the
  // shopper back to the start rather than rendering an empty shelf.
  if (!recommendation) return <Navigate to="/create" replace />

  const relaxed = recommendation.relaxed_constraints

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-6 py-16">
        <header className="flex flex-col gap-4">
          <p className="eyebrow">Your looks</p>
          <h1 className="text-title text-ink-950">
            Three outfits for {recommendation.occasion.toLowerCase()}
            {style ? `, in a ${style.toLowerCase()} register` : ''}
          </h1>
          <p className="text-sm text-ink-700">
            Ranked against a budget of {formatInr(budgetInr ?? recommendation.budget_inr)}.
          </p>
        </header>

        {recommendation.notice && (
          <div className="mt-8 border-l-2 border-accent-600 bg-accent-100/40 px-5 py-4">
            <p className="text-sm text-accent-700">{recommendation.notice}</p>
            {relaxed.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1">
                {relaxed.map((item) => (
                  <li key={item} className="text-xs text-accent-700/90">
                    &middot; {item}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {recommendation.looks.map((look) => (
            <LookCard
              key={look.look_id}
              look={look}
              budgetInr={recommendation.budget_inr}
            />
          ))}
        </div>

        <div className="mt-12 flex flex-wrap items-center gap-4 border-t border-ink-200 pt-8">
          <Button
            variant="secondary"
            onClick={reset}
            title="Clears your answers and photo from this tab"
          >
            Start over
          </Button>
          <p className="text-xs text-ink-500">
            Answers stay in this tab only. Closing it clears everything.
          </p>
        </div>
      </div>
    </AppShell>
  )
}
