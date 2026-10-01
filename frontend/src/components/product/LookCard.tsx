/**
 * One recommended look, as the shopper sees it on the results grid.
 *
 * The layout is editorial on purpose: the garments lead, the price sits small
 * and quiet underneath, and the score breakdown is folded away rather than
 * shouting percentage bars at someone trying to picture themselves in an outfit.
 */

import { Link } from 'react-router-dom'

import type { LookRecommendation } from '@/api/types'
import { ProductImage } from '@/components/product/ProductTile'
import { formatInr } from '@/lib/format'

/** The four slots in the order an outfit is read top to bottom. */
const SLOT_ORDER = ['top', 'bottom', 'footwear', 'accessory'] as const

export function LookCard({
  look,
  budgetInr,
}: {
  look: LookRecommendation
  /** The shopper's budget, so the card can flag a relaxed result honestly. */
  budgetInr: number
}) {
  const bySlot = new Map(look.items.map((item) => [item.slot, item]))
  const ordered = SLOT_ORDER.map((slot) => bySlot.get(slot)).filter(
    (item): item is NonNullable<typeof item> => Boolean(item),
  )
  const hero = bySlot.get('top') ?? ordered[0]
  const overBudget = look.total_price_inr > budgetInr

  return (
    <article className="group flex flex-col border border-ink-200 bg-white">
      <Link to={`/look/${look.look_id}`} className="flex flex-1 flex-col">
        <div className="relative aspect-4/5 overflow-hidden bg-paper-deep">
          <ProductImage
            product={hero}
            className="size-full transition-transform duration-700 group-hover:scale-[1.03]"
          />
          <span className="absolute top-3 left-3 bg-paper/90 px-2.5 py-1 text-[0.6875rem] font-medium tracking-[0.18em] text-ink-700 uppercase backdrop-blur">
            Look {look.rank}
          </span>
        </div>

        <div className="flex flex-1 flex-col gap-3 p-5">
          {/* The hero garment is the only one shown large; the rest are a
              compact row, which is enough to recognise the outfit without
              turning the card into a product grid. */}
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium text-ink-950">{hero.name}</p>
            {ordered.length > 1 && (
              <p className="text-xs text-ink-500">
                +{ordered.length - 1} more{' '}
                {ordered.length - 1 === 1 ? 'piece' : 'pieces'}
              </p>
            )}
          </div>

          <p className="text-lg font-medium text-ink-950">
            {formatInr(look.total_price_inr)}
          </p>

          {look.reasons.length > 0 && (
            <ul className="flex flex-col gap-1">
              {look.reasons.slice(0, 2).map((reason) => (
                <li key={reason} className="text-xs text-ink-700">
                  {reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Link>

      <div className="flex items-center justify-between gap-3 border-t border-ink-100 px-5 py-3">
        <span className="text-xs tracking-wide text-ink-500 uppercase">
          {Math.round(look.score.total * 100)}% match
        </span>
        <Link
          to={`/look/${look.look_id}`}
          className="text-sm font-medium text-ink-950 underline underline-offset-4 group-hover:text-accent-600"
        >
          See the look
        </Link>
      </div>

      {overBudget && (
        <p className="border-t border-accent-500/20 bg-accent-100/40 px-5 py-2 text-xs text-accent-700">
          Over your budget
        </p>
      )}
    </article>
  )
}
