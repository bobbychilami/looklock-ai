/**
 * One look in full: the outfit as a picture, every garment with its real role, and
 * two deliberately separate destinations.
 *
 * The two actions are not variants of one another and are not merged:
 *
 * - "See it on me" is the try-on. It needs a photo, it sends the shopper's image to
 *   a third party, and it produces a picture of them wearing the outfit.
 * - "Shop this look" is buying. It opens the breakdown where each garment links to
 *   its retailer, and it sends the shopper away from LOOKLOCK entirely.
 *
 * Collapsing them into a single "Continue" would hide a consent boundary and a
 * departure, which is why they are separate buttons with different weight.
 */

import { Navigate, Link, useNavigate, useParams } from 'react-router-dom'

import type { LookScore } from '@/api/types'
import { AppShell } from '@/components/layout/AppShell'
import { BudgetNotice } from '@/components/product/BudgetNotice'
import { DemoImageryTag, LookVisual } from '@/components/product/LookVisual'
import { ProductTile } from '@/components/product/ProductTile'
import { Button } from '@/components/ui/Button'
import { formatInr, formatScore } from '@/lib/format'
import { useLookSession } from '@/state/looklock'

/** The weights the backend actually applies, kept in step with `engine.py`. */
const SCORE_COMPONENTS: { key: keyof Omit<LookScore, 'total'>; label: string; weight: string }[] = [
  { key: 'occasion', label: 'Fits the occasion', weight: '35%' },
  { key: 'style', label: 'Matches your style', weight: '25%' },
  { key: 'budget', label: 'Uses your budget well', weight: '25%' },
  { key: 'completeness', label: 'Complete outfit', weight: '15%' },
]

export default function LookDetail() {
  const { lookId } = useParams<{ lookId: string }>()
  const navigate = useNavigate()
  const { recommendation, budgetInr, canBuild, photo } = useLookSession()

  if (!recommendation) return <Navigate to="/create" replace />

  const look = recommendation.looks.find((candidate) => candidate.look.look_id === lookId)
  if (!look) return <Navigate to="/looks" replace />

  const heroView = look.heroView
  const items = look.productViews
  const effectiveBudget = budgetInr ?? recommendation.budgetInr

  /** Preserves the existing VTO path: the hero product's id is the route param
   *  the try-on page already reads, so nothing about that flow changes. */
  function startTryOn() {
    if (!heroView) return
    navigate(`/tryon/${heroView.item.product_id}`, { state: { lookId: look?.look.look_id } })
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-6 py-16">
        <Link to="/looks" className="text-sm text-ink-500 underline underline-offset-4">
          &larr; All your looks
        </Link>

        <div className="mt-8 grid gap-12 lg:grid-cols-[1fr_1.05fr]">
          {/* The look as a picture, then the garment the try-on will use. */}
          <div className="flex flex-col gap-4">
            <div className="relative overflow-hidden rounded-editorial border border-ink-200 bg-white">
              <LookVisual look={look} className="aspect-4/5 w-full" />
              <DemoImageryTag demo={look.hasDemoImagery} />
            </div>
            {heroView && (
              <div className="flex flex-col gap-1.5">
                <p className="eyebrow">Try-on reference · {heroView.role}</p>
                <p className="font-display text-lg text-ink-950">{heroView.item.name}</p>
                <p className="text-sm text-ink-700">{heroView.item.description}</p>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-10">
            <header className="flex flex-col gap-3">
              <p className="eyebrow">Look {look.look.rank}</p>
              <h1 className="font-display text-4xl leading-tight text-ink-950">{look.name}</h1>
              <p className="text-sm text-ink-700">{look.summary}</p>
              <p className="font-display text-2xl text-ink-950">
                {look.price}
                <span className="ml-2 text-sm font-sans text-ink-500">
                  total, {look.pieceCount} {look.pieceCount === 1 ? 'piece' : 'pieces'}
                </span>
              </p>
            </header>

            {look.overBudget && (
              <div
                role="status"
                data-budget-state="over"
                className="border-l-2 border-accent-600 bg-accent-100/40 px-5 py-4"
              >
                <p className="text-sm font-medium text-accent-700">
                  Over your {formatInr(effectiveBudget)} budget by {formatInr(look.overByInr)}.
                </p>
                {/* The explanation depends on *why* the look is over: a catalogue
                    with nothing in range is a different situation from a set where
                    some looks fit and this one does not, and saying "nothing
                    appropriate at that price" about the second would be a lie the
                    shopper could disprove from the page above. */}
                <p className="mt-1.5 text-sm text-accent-700">
                  {recommendation.budget.status === 'partial'
                    ? 'Other looks in this set do fit your budget.'
                    : 'Every piece suits the occasion; this catalogue has nothing appropriate at that price.'}
                </p>
              </div>
            )}

            {/* --- The two actions, kept apart on purpose --- */}
            <div className="flex flex-col gap-3 border-y border-ink-200 py-6">
              <Button
                onClick={startTryOn}
                size="lg"
                data-action="see-it-on-me"
                disabled={!canBuild || !heroView?.tryonReady}
              >
                See it on me
              </Button>
              <p className="text-xs text-ink-500">
                {heroView?.tryonRemoteImage
                  ? 'This piece is only pictured on a retailer page, so the try-on service cannot use it as a reference yet. Try-on is unavailable for this look.'
                  : heroView?.tryonCapable === false
                    ? 'The try-on needs a single garment, so it works from the reference piece above.'
                    : 'Uses your photo with the YouCam virtual try-on. Your image is sent to that service and is not stored by LOOKLOCK.'}
              </p>

              {!canBuild && (
                <p className="text-xs leading-relaxed text-ink-500">
                  {!photo
                    ? 'Add a photo and accept the consent step in the wizard to unlock the try-on.'
                    : 'Finish the photo consent step in the wizard to unlock the try-on.'}
                </p>
              )}

              <Link
                to="/shop"
                state={{ lookId: look.look.look_id }}
                data-action="shop-this-look"
                className="mt-2 inline-flex w-fit items-center gap-2 border border-ink-300 px-5 py-2.5 text-sm font-medium text-ink-900 transition-colors hover:border-ink-900 hover:bg-paper-deep"
              >
                Shop this look
                <span aria-hidden>&rarr;</span>
              </Link>
              <p className="text-xs text-ink-500">
                {look.isShoppable
                  ? `Every piece is listed with a retailer${
                      look.retailerNames.length ? ` (${look.retailerNames.join(', ')})` : ''
                    }. Each opens in a new tab.`
                  : 'Opens the breakdown below with retailer links where they exist.'}
              </p>
            </div>

            {look.look.reasons.length > 0 && (
              <section className="flex flex-col gap-3">
                <p className="eyebrow">Why this look</p>
                <ul className="flex flex-col gap-2">
                  {look.look.reasons.map((reason) => (
                    <li key={reason} className="flex gap-3 text-sm text-ink-700">
                      <span className="mt-2 size-1 shrink-0 rounded-full bg-accent-500" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="flex flex-col gap-3">
              <p className="eyebrow">How it scored</p>
              <dl className="flex flex-col">
                {SCORE_COMPONENTS.map((component) => (
                  <div
                    key={component.key}
                    className="flex items-baseline justify-between gap-4 border-b border-ink-100 py-2.5 last:border-b-0"
                  >
                    <dt className="text-sm text-ink-700">
                      {component.label}{' '}
                      <span className="text-xs text-ink-500">({component.weight} weight)</span>
                    </dt>
                    <dd className="text-sm font-medium text-ink-950">
                      {formatScore(look.look.score[component.key])}
                    </dd>
                  </div>
                ))}
                <div className="flex items-baseline justify-between gap-4 border-t border-ink-300 py-3">
                  <dt className="text-sm font-medium text-ink-950">Overall</dt>
                  <dd className="font-display text-lg text-ink-950">
                    {formatScore(look.look.score.total)}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="flex flex-col gap-3">
              <p className="eyebrow">What you&rsquo;d need</p>
              <ul className="flex flex-col" aria-label={`Pieces in ${look.name}`}>
                {items.map((item) => (
                  <ProductTile key={item.item.product_id} view={item} />
                ))}
              </ul>
              <div className="flex items-baseline justify-between gap-4 border-t border-ink-300 pt-3">
                <span className="text-sm font-medium text-ink-950">Total</span>
                <span className="font-display text-xl text-ink-950">{look.price}</span>
              </div>
            </section>

            {/* Whole-response budget state, so the detail page never claims the
                result is affordable when the page above it said otherwise. */}
            <BudgetNotice budget={recommendation.budget} />
          </div>
        </div>
      </div>
    </AppShell>
  )
}
