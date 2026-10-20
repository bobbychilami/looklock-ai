/**
 * Product artwork and the compact garment rows used in a look's breakdown.
 *
 * `ProductTile` is where the backend's shopping metadata becomes visible: the
 * retailer name, and a link only when the backend supplied a verified URL. When
 * there is nothing verified the row still renders in full - the shopper still
 * needs to know what the garment is and what it costs - it just does not get a
 * button pointing at nothing.
 */

import { ResilientImage } from '@/components/product/ResilientImage'
import { availabilityLabel, type ProductView } from '@/api/normalize'
import type { ScoredProduct } from '@/api/types'

export function ProductImage({
  product,
  className = '',
}: {
  product: Pick<ScoredProduct, 'product_id' | 'name' | 'image_url'>
  className?: string
}) {
  return (
    <ResilientImage
      src={product.image_url}
      alt={product.name}
      productId={product.product_id}
      // The bundled artwork is a fixed 4:5 portrait; reserving the box keeps the
      // grid from reflowing as images stream in.
      className={`bg-paper-deep object-cover ${className}`}
    />
  )
}

/**
 * One garment in a look's breakdown.
 *
 * The role comes from the backend's normalised `slot`, never parsed out of the
 * product name: "Ivory Churidar" as a top and "Ivory Churidar" as a bottom are the
 * same words and different garments, and only the server knows which.
 */
export function ProductTile({ view }: { view: ProductView }) {
  const { item } = view

  return (
    <li
      data-slot={item.slot}
      className="flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-ink-100 py-5 last:border-b-0 sm:flex-nowrap"
    >
      <ProductImage product={item} className="size-24 shrink-0 rounded-editorial" />

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-[0.6875rem] font-medium tracking-[0.18em] text-ink-500 uppercase">
          {view.role}
        </p>
        <p className="font-display text-lg leading-snug text-ink-950 break-words">{item.name}</p>
        {item.subcategory && (
          <p className="text-xs text-ink-500">
            {item.category ? `${item.category} · ${item.subcategory}` : item.subcategory}
          </p>
        )}
        <p className="text-sm font-medium text-ink-900">{view.price}</p>

        {view.retailerName && (
          <p className="text-xs text-ink-700">
            Retailer: <span className="break-words">{view.retailerName}</span>
          </p>
        )}
      </div>

      <div className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
        {view.shopUrl ? (
          <a
            href={view.shopUrl}
            target="_blank"
            rel="noopener noreferrer"
            data-shop-link="true"
            className="text-sm font-medium text-ink-950 underline underline-offset-4 hover:text-accent-600"
          >
            {(view as any).productLinkType === 'google_shopping' || (!view.retailerName && !((view as any).productLinkType === 'direct_retailer'))
              ? 'View Product'
              : `Shop at ${view.retailerName ?? 'retailer'}`} &rarr;
          </a>
        ) : view.isDemo ? (
          <span className="text-xs tracking-wide text-ink-500 uppercase">Demo</span>
        ) : (
          <span className="text-xs tracking-wide text-ink-500 uppercase">No link yet</span>
        )}
        {availabilityLabel(view.availability) && (
          // The link stays. A shopper told "out of stock" with no way to check
          // would be worse off than one sent to the listing page, which is the
          // authoritative place for restock and alternatives.
          <span
            data-availability={view.availability}
            className="text-[0.6875rem] tracking-wide text-ink-700 uppercase"
          >
            {availabilityLabel(view.availability)}
          </span>
        )}
        {item.retailer && !item.can_shop && (
          <span className="text-[0.6875rem] text-ink-500">No verified listing URL</span>
        )}
      </div>
    </li>
  )
}
