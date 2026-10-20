/**
 * "Your Looks": the ranked outfits.
 *
 * The budget state and the engine's notice sit above the grid, not underneath it.
 * If the catalogue could not honour the budget, that is the first thing to read -
 * a shopper who scrolls to three cheerful cards first has already been misled.
 *
 * Each card carries its own budget state as well, so the answer to "can I afford
 * this one?" is available at the point of choosing rather than only here.
 */

import { Navigate } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { BudgetNotice } from '@/components/product/BudgetNotice'
import { LookCard } from '@/components/product/LookCard'
import { Button } from '@/components/ui/Button'
import { formatInr } from '@/lib/format'
import { useLookSession } from '@/state/looklock'

export default function Looks() {
  const { budgetInr, recommendation, reset } = useLookSession()

  // Arriving without a recommendation means the session was lost, so send the
  // shopper back to the start rather than rendering an empty shelf.
  if (!recommendation) return <Navigate to="/create" replace />

  const { budget, looks } = recommendation
  const shoppableLooks = looks.filter((look) => look.isShoppable).length

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-6 py-16">
        <header className="flex flex-col gap-4">
          <p className="eyebrow">Your looks</p>
          <h1 className="text-title text-ink-950">
            {looks.length === 1 ? 'One outfit' : `${looks.length} outfits`} for{' '}
            {recommendation.occasion.toLowerCase()}
            {recommendation.style ? `, in a ${recommendation.style.toLowerCase()} register` : ''}
          </h1>
          <p className="text-sm text-ink-700">
            Ranked against a budget of {formatInr(budgetInr ?? recommendation.budgetInr)}.
            {recommendation.hasDemoImagery && ' Product imagery here is illustrative.'}
          </p>
        </header>

        <BudgetNotice budget={budget} className="mt-8" />

        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {looks.map((look) => (
            <LookCard key={look.look.look_id} look={look} />
          ))}
        </div>

        <div className="mt-12 flex flex-wrap items-center gap-4 border-t border-ink-200 pt-8">
          <Button variant="secondary" onClick={reset} title="Clears your answers and photo from this tab">
            Start over
          </Button>
          <p className="text-xs text-ink-500">
            {shoppableLooks > 0
              ? `${shoppableLooks} of ${looks.length} looks can be bought in full.`
              : 'No retailer listings are connected to this catalogue yet, so nothing here can be bought.'}{' '}
            Answers stay in this tab only. Closing it clears everything.
          </p>
        </div>
      </div>
    </AppShell>
  )
}
