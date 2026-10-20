/**
 * One recommended look, as the shopper sees it on the results grid.
 *
 * A card represents a *complete outfit*, so three things changed when the backend
 * grew a real look model:
 *
 * - The picture comes from `LookVisual`. The old card showed `items[0].image`,
 *   which meant a sherwani with a churidar, mojari and pocket square was pictured
 *   as a shirt. It is now the layered composition of every piece in the look.
 * - The title is the backend's look name. Calling a look "Ivory Poplin Shirt"
 *   described one of five garments and implied the rest were optional.
 * - Budget state is stated per card, with the shopper's real budget, so an
 *   over-budget result is visible where it is being considered rather than only
 *   in a notice at the top of the page.
 */

import { Link } from 'react-router-dom'

import type { LookView } from '@/api/normalize'
import { DemoImageryTag, LookVisual } from '@/components/product/LookVisual'
import { formatInr } from '@/lib/format'

export function LookCard({ look }: { look: LookView }) {
  return (
    <article className="group flex flex-col border border-ink-200 bg-white">
      <Link to={`/look/${look.look.look_id}`} className="flex flex-1 flex-col">
        <div className="relative aspect-4/5 overflow-hidden bg-paper-deep">
          <LookVisual
            look={look}
            className="transition-transform duration-700 group-hover:scale-[1.03]"
          />
          <span className="absolute top-3 left-3 bg-paper/90 px-2.5 py-1 text-[0.6875rem] font-medium tracking-[0.18em] text-ink-700 uppercase backdrop-blur">
            Look {look.look.rank}
          </span>
          <DemoImageryTag demo={look.hasDemoImagery} />
        </div>

        <div className="flex flex-1 flex-col gap-2 p-5">
          <div className="flex flex-col gap-1">
            <h3 className="font-display text-lg leading-tight text-ink-950">{look.name}</h3>
            <p className="text-xs text-ink-500">{look.summary}</p>
          </div>

          <p className="font-display text-xl text-ink-950">{look.price}</p>

          <ul className="flex flex-col gap-1">
            {look.look.reasons.slice(0, 2).map((reason) => (
              <li key={reason} className="text-xs text-ink-700">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      </Link>

      {/* Price and fit sit on one quiet line; the budget state gets its own row
          because it changes what the shopper should do next. */}
      <div className="flex items-center justify-between gap-3 border-t border-ink-100 px-5 py-3">
        <span className="text-xs tracking-wide text-ink-500 uppercase">
          {look.matchPercent}% match
        </span>
        <span className="text-sm font-medium text-ink-950 underline underline-offset-4 group-hover:text-accent-600">
          See the look &rarr;
        </span>
      </div>

      {look.overBudget && (
        <p
          data-budget-state="over"
          className="border-t border-accent-500/20 bg-accent-100/40 px-5 py-2 text-xs text-accent-700"
        >
          Over your {formatInr(look.budgetInr)} budget by {formatInr(look.overByInr)}
        </p>
      )}
    </article>
  )
}
