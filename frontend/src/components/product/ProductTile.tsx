/**
 * Product artwork, resolved through `assetUrl` so the component works whether
 * the API is on the same origin (dev proxy, production reverse proxy) or on a
 * separate host.
 */

import { assetUrl } from '@/config/env'
import type { ScoredProduct } from '@/api/types'
import { formatInr, slotLabel } from '@/lib/format'

export function ProductImage({
  product,
  className = '',
}: {
  product: Pick<ScoredProduct, 'name' | 'image_url'>
  className?: string
}) {
  return (
    <img
      src={assetUrl(product.image_url)}
      alt={product.name}
      // The bundled artwork is a fixed 4:5 portrait; reserving the box keeps the
      // grid from reflowing as images stream in.
      className={`bg-paper-deep object-cover ${className}`}
      loading="lazy"
    />
  )
}

/** Compact garment card used in the shop-this-look breakdown. */
export function ProductTile({ product }: { product: ScoredProduct }) {
  return (
    <li className="flex items-center gap-4 border-b border-ink-100 py-4 last:border-b-0">
      <ProductImage product={product} className="size-20 shrink-0 rounded-editorial" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-xs tracking-wide text-ink-500 uppercase">{slotLabel(product.slot)}</p>
        <p className="truncate font-medium text-ink-950">{product.name}</p>
        <p className="truncate text-sm text-ink-700">{product.description}</p>
        <p className="text-sm font-medium text-ink-900">{formatInr(product.price_inr)}</p>
      </div>
      {/* Only real listings would get a link; the demo catalogue has none, and
          inventing a retailer URL would misrepresent a product that does not
          exist. */}
      {product.purchase_url ? (
        <a
          href={product.purchase_url}
          target="_blank"
          rel="noreferrer noopener"
          className="shrink-0 text-sm font-medium text-accent-600 underline underline-offset-4"
        >
          Buy
        </a>
      ) : (
        <span className="shrink-0 text-xs tracking-wide text-ink-500 uppercase">Demo</span>
      )}
    </li>
  )
}
