/**
 * One look in full: every garment, the score that earned the rank, and the way
 * into the try-on.
 *
 * The score breakdown is shown as a labelled list rather than bars. Percentages
 * on bars invite the reader to compare four numbers that are weighted
 * differently, which is not a useful thing to do; naming each component and its
 * weight is.
 */

import { Navigate, Link, useNavigate, useParams } from 'react-router-dom'

import type { LookScore } from '@/api/types'
import { AppShell } from '@/components/layout/AppShell'
import { ProductImage, ProductTile } from '@/components/product/ProductTile'
import { Button } from '@/components/ui/Button'
import { formatInr, formatScore, slotLabel } from '@/lib/format'
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

  const look = recommendation.looks.find((candidate) => candidate.look_id === lookId)
  if (!look) return <Navigate to="/looks" replace />

  const hero = look.items.find((item) => item.product_id === look.hero_product_id)
  const overBudget = look.total_price_inr > recommendation.budget_inr

  function startTryOn() {
    if (!hero) return
    navigate(`/tryon/${hero.product_id}`, { state: { lookId: look?.look_id } })
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-6 py-16">
        <Link to="/looks" className="text-sm text-ink-500 underline underline-offset-4">
          &larr; All your looks
        </Link>

        <div className="mt-8 grid gap-12 lg:grid-cols-[1fr_1.1fr]">
          {/* Hero garment */}
          <div className="flex flex-col gap-4">
            {hero && (
              <div className="overflow-hidden rounded-editorial border border-ink-200 bg-white">
                <ProductImage product={hero} className="aspect-4/5 w-full" />
              </div>
            )}
            {hero && (
              <div className="flex flex-col gap-1">
                <p className="eyebrow">{slotLabel(hero.slot)}</p>
                <h2 className="font-display text-xl text-ink-950">{hero.name}</h2>
                <p className="text-sm text-ink-700">{hero.description}</p>
                <p className="text-sm font-medium text-ink-900">{formatInr(hero.price_inr)}</p>
              </div>
            )}
          </div>

          {/* Everything else about the look */}
          <div className="flex flex-col gap-10">
            <header className="flex flex-col gap-3">
              <p className="eyebrow">Look {look.rank}</p>
              <h1 className="text-title text-ink-950">The complete outfit</h1>
              <p className="font-display text-2xl text-ink-950">
                {formatInr(look.total_price_inr)}
                <span className="ml-2 text-sm text-ink-500">total</span>
              </p>
              {overBudget && (
                <p className="text-sm text-accent-700">
                  This is over your {formatInr(budgetInr ?? recommendation.budget_inr)} budget,
                  because the catalogue could not fill the outfit within it.
                </p>
              )}
            </header>

            {look.reasons.length > 0 && (
              <section className="flex flex-col gap-3">
                <p className="eyebrow">Why this look</p>
                <ul className="flex flex-col gap-2">
                  {look.reasons.map((reason) => (
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
                      {formatScore(look.score[component.key])}
                    </dd>
                  </div>
                ))}
                <div className="flex items-baseline justify-between gap-4 border-t border-ink-300 py-3">
                  <dt className="text-sm font-medium text-ink-950">Overall</dt>
                  <dd className="font-display text-lg text-ink-950">
                    {formatScore(look.score.total)}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="flex flex-col gap-3">
              <p className="eyebrow">What you&rsquo;d need</p>
              <ul className="flex flex-col">
                {look.items.map((item) => (
                  <ProductTile key={item.product_id} product={item} />
                ))}
              </ul>
            </section>

            <div className="flex flex-col gap-3 border-t border-ink-200 pt-8">
              <Button onClick={startTryOn} size="lg" disabled={!hero || !hero.is_tryon_capable}>
                Try the {hero ? slotLabel(hero.slot).toLowerCase() : 'top'} on
              </Button>
              {!canBuild && (
                <p className="text-xs leading-relaxed text-ink-500">
                  {!photo
                    ? 'Add a photo and accept the consent step in the wizard to unlock the try-on.'
                    : 'Finish the photo consent step in the wizard to unlock the try-on.'}
                </p>
              )}
              <Link
                to="/shop"
                className="text-center text-sm text-ink-700 underline underline-offset-4"
              >
                Skip and see the price breakdown
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
