/**
 * "Shop this look": the full price breakdown.
 *
 * Every product here is fictional, so there is nothing to buy and the page says
 * so at the top. A breakdown is still worth showing even for a demo - it is the
 * part that tells someone whether the styling respects their budget, which is
 * the actual decision LOOKLOCK is meant to support.
 */

import { Navigate, Link, useLocation } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { ProductImage } from '@/components/product/ProductTile'
import { Badge } from '@/components/ui/Badge'
import { formatInr } from '@/lib/format'
import { useLookSession } from '@/state/looklock'

/** `state` passed from the look detail page, so the breakdown knows its source. */
interface LookLocationState {
  state?: { lookId?: string }
}

export default function Shop() {
  const { recommendation, budgetInr } = useLookSession()
  const location = useLocation()
  const { lookId } = (location.state as LookLocationState | null)?.state ?? {}

  if (!recommendation) return <Navigate to="/create" replace />

  // Default to the top-ranked look so the page is never a dead end.
  const look =
    recommendation.looks.find((candidate) => candidate.look_id === lookId) ??
    recommendation.looks[0]

  if (!look) return <Navigate to="/looks" replace />

  const remaining = recommendation.budget_inr - look.total_price_inr
  const items = look.items

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl px-6 py-16">
        <header className="flex flex-col gap-4">
          <p className="eyebrow">Shop this look</p>
          <h1 className="text-title text-ink-950">Your complete breakdown</h1>
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone="warn">Demo catalogue</Badge>
            <p className="text-sm text-ink-700">
              No product below is real and none is for sale. The breakdown is here to show the
              styling maths.
            </p>
          </div>
        </header>

        {/* Total */}
        <dl className="mt-10 border-y border-ink-200">
          <div className="flex items-baseline justify-between gap-4 py-4">
            <dt className="text-sm text-ink-700">Your budget</dt>
            <dd className="text-sm text-ink-900">
              {formatInr(budgetInr ?? recommendation.budget_inr)}
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-4 border-t border-ink-100 py-4">
            <dt className="text-sm text-ink-700">
              {items.length} {items.length === 1 ? 'piece' : 'pieces'}
            </dt>
            <dd className="font-display text-2xl text-ink-950">
              {formatInr(look.total_price_inr)}
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-4 border-t border-ink-200 py-4">
            <dt className="text-sm font-medium text-ink-950">
              {remaining >= 0 ? 'Left from your budget' : 'Over your budget'}
            </dt>
            <dd
              className={`text-sm font-medium ${remaining >= 0 ? 'text-ink-950' : 'text-accent-700'}`}
            >
              {formatInr(Math.abs(remaining))}
            </dd>
          </div>
        </dl>

        {/* Items */}
        <ul className="mt-10 flex flex-col gap-6">
          {items.map((item) => (
            <li key={item.product_id} className="flex gap-5">
              <ProductImage
                product={item}
                className="size-28 shrink-0 rounded-editorial border border-ink-200"
              />
              <div className="flex flex-1 flex-col gap-1.5">
                <p className="eyebrow">{item.slot}</p>
                <p className="font-display text-lg text-ink-950">{item.name}</p>
                <p className="text-sm text-ink-700">{item.description}</p>
                <p className="text-sm font-medium text-ink-900">{formatInr(item.price_inr)}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {item.matches_occasion && <Badge tone="ok">Fits your occasion</Badge>}
                  {item.matches_style && <Badge tone="ok">Matches your style</Badge>}
                  {!item.is_tryon_capable && <Badge tone="neutral">Accessory</Badge>}
                </div>
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-12 flex flex-col items-center gap-3 border-t border-ink-200 pt-8">
          <Link
            to={`/look/${look.look_id}`}
            className="text-sm text-ink-700 underline underline-offset-4"
          >
            Back to the look
          </Link>
          <Link to="/looks" className="text-sm text-ink-500 underline underline-offset-4">
            See your other looks
          </Link>
        </div>
      </div>
    </AppShell>
  )
}
