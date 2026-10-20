/**
 * "Shop this look": the retailer-facing side of a look.
 *
 * Reached from the secondary action on the look detail page. Its job is to
 * coordinate the individual purchase links in one place rather than firing five
 * browser popups, and to be honest when there is nothing to buy.
 *
 * The demo catalogue has no verified listings, so on a stock deployment this page
 * says so and shows no buttons. Links appear only for products where the backend
 * reported both a retailer and a URL (`can_shop`); no URL is ever constructed here.
 */

import { Navigate, Link, useLocation } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { LookVisual } from '@/components/product/LookVisual'
import { ResilientImage } from '@/components/product/ResilientImage'
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
    recommendation.looks.find((candidate) => candidate.look.look_id === lookId) ??
    recommendation.looks[0]

  if (!look) return <Navigate to="/looks" replace />

  const remaining = recommendation.budgetInr - look.look.total_price_inr
  const views = look.productViews

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl px-6 py-16">
        <header className="flex flex-col gap-4">
          <p className="eyebrow">Shop this look</p>
          <h1 className="font-display text-3xl text-ink-950">{look.name}</h1>
          <p className="text-sm text-ink-700">
            {look.summary} · {look.price} total
          </p>

          {look.hasDemoImagery && (
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone="warn">Demo catalog</Badge>
              <p className="text-sm text-ink-700">
                {look.isShoppable
                  ? 'The imagery is illustrative, but the listings below are real.'
                  : 'No product below is a live listing. The breakdown shows the styling maths and the roles each piece plays.'}
              </p>
            </div>
          )}
        </header>

        <div className="relative mt-8 overflow-hidden rounded-editorial border border-ink-200 bg-white">
          <LookVisual look={look} className="aspect-4/5 w-full" />
        </div>

        {/* Budget, stated the same way the results page states it. */}
        <dl className="mt-10 border-y border-ink-200">
          <div className="flex items-baseline justify-between gap-4 py-4">
            <dt className="text-sm text-ink-700">Your budget</dt>
            <dd className="text-sm text-ink-900">
              {formatInr(budgetInr ?? recommendation.budgetInr)}
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-4 border-t border-ink-100 py-4">
            <dt className="text-sm text-ink-700">
              {look.pieceCount} {look.pieceCount === 1 ? 'piece' : 'pieces'}
            </dt>
            <dd className="font-display text-2xl text-ink-950">{look.price}</dd>
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

        {/* Retailer links, or an honest account of their absence. */}
        <section className="mt-10">
          {look.shoppableItems.length > 0 ? (
            <>
              <p className="eyebrow">Where to buy</p>
              <ul className="mt-3 flex flex-col gap-3">
                {views
                  .filter((view) => view.shopUrl)
                  .map((view) => (
                    <li key={view.item.product_id}>
                      <a
                        href={view.shopUrl as string}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-shop-link="true"
                        className="flex items-center justify-between gap-4 border border-ink-200 px-5 py-4 transition-colors hover:border-ink-500"
                      >
                        <span className="flex min-w-0 flex-col gap-1">
                          <span className="text-xs tracking-wide text-ink-500 uppercase">
                            {view.item.subcategory ?? view.item.slot}
                          </span>
                          <span className="font-medium text-ink-950 break-words">
                            {view.item.name}
                          </span>
                        </span>
                        <span className="shrink-0 text-sm font-medium text-ink-950 underline underline-offset-4">
                          Shop at {view.retailerName} &rarr;
                        </span>
                      </a>
                    </li>
                  ))}
              </ul>
              {look.shoppableItems.length < views.length && (
                <p className="mt-4 text-xs text-ink-500">
                  {views.length - look.shoppableItems.length} of {views.length} pieces have no
                  verified retailer listing yet, so there is no link to follow for them.
                </p>
              )}
            </>
          ) : (
            <div className="border border-ink-200 bg-paper-deep px-5 py-6">
              <p className="text-sm font-medium text-ink-950">Nothing to link to yet</p>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-700">
                LOOKLOCK has no retailer connected for this catalogue, so no piece below has a
                purchase page we can vouch for. Inventing a link to a product that does not exist
                would be worse than showing none.
              </p>
            </div>
          )}
        </section>

        {/* Every piece, in dressing order, whatever its shopping state. */}
        <section className="mt-12">
          <p className="eyebrow">Every piece in this look</p>
          <ul className="mt-3 flex flex-col divide-y divide-ink-100">
            {views.map((view) => (
              <li key={view.item.product_id} data-slot={view.item.slot} className="flex gap-5 py-5">
                <ResilientImage
                  src={view.item.image_url}
                  alt={view.item.name}
                  productId={view.item.product_id}
                  className="size-24 shrink-0 rounded-editorial border border-ink-200 object-cover"
                />
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <p className="text-[0.6875rem] font-medium tracking-[0.18em] text-ink-500 uppercase">
                    {view.item.subcategory ?? view.item.slot}
                  </p>
                  <p className="font-display text-lg text-ink-950 break-words">{view.item.name}</p>
                  <p className="text-sm text-ink-700">{view.item.description}</p>
                  <p className="text-sm font-medium text-ink-900">{view.price}</p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {view.retailerName && <Badge tone="neutral">{view.retailerName}</Badge>}
                    {view.item.matches_occasion && <Badge tone="ok">Fits your occasion</Badge>}
                    {view.item.matches_style && <Badge tone="ok">Matches your style</Badge>}
                    {!view.item.is_tryon_capable && <Badge tone="neutral">Not try-on eligible</Badge>}
                    {view.tryonRemoteImage && (
                      <Badge tone="neutral">Try-on unavailable for retailer image</Badge>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <div className="mt-12 flex flex-col items-center gap-3 border-t border-ink-200 pt-8">
          <Link
            to={`/look/${look.look.look_id}`}
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
