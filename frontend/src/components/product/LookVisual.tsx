/**
 * The picture of a look.
 *
 * Three tiers, in the order the backend decides them:
 *
 * 1. `complete_look` - a styled shot the provider supplied. This is a real
 *    photograph of the outfit, so it is shown as one image.
 * 2. `composite` - no styled shot exists, so the look is shown as its own pieces,
 *    each in its own cell and captioned with its role.
 * 3. `grid` - nothing usable, so the pieces are laid out as a plain grid.
 *
 * The thing this component must never do is present one garment as though it were
 * the whole outfit. That was the old behaviour: the card showed `items[0].image`,
 * so a sherwani and churidar and mojari outfit was captioned and pictured as a
 * shirt. When a `LookVisual` is present it is authoritative, and the first
 * product image is only ever a last resort.
 *
 * On composition: an earlier version stacked the pieces as overlapping layers
 * centred on one point. Real garment crops are framed on their own garments, not
 * on a shared torso, so every piece landed on top of the others and three
 * genuinely different looks all read as the same grey pile. Each piece now gets
 * its own cell - a flat-lay rather than a pile - so what is on the card is
 * legible and two different looks cannot look identical.
 */

import { assetUrl } from '@/config/env'
import { ResilientImage } from '@/components/product/ResilientImage'
import { roleLabel } from '@/api/normalize'
import type { LookView } from '@/api/normalize'

interface LookVisualProps {
  look: LookView
  /** Extra classes for the frame, e.g. to make it fill a grid cell. */
  className?: string
}

export function LookVisual({ look, className = '' }: LookVisualProps) {
  const { look: raw } = look
  const alt = raw.visual.alt || `${raw.name}, a complete look of ${raw.items.length} pieces`

  if (raw.visual.kind === 'complete_look' && raw.visual.image_url) {
    return (
      <img
        src={assetUrl(raw.visual.image_url)}
        alt={alt}
        data-visual-kind="complete_look"
        className={`size-full bg-paper-deep object-cover ${className}`}
        loading="lazy"
      />
    )
  }

  if (raw.visual.kind === 'composite' && raw.visual.layers.length > 0) {
    const layers = raw.visual.layers
    const single = layers.length === 1
    // An odd piece count leaves a gap in the last row; letting the final piece
    // span both columns keeps the flat-lay rectangular instead of ragged.
    const fillLast = !single && layers.length % 2 === 1
    return (
      <div
        className={`grid size-full auto-rows-fr gap-px bg-ink-200 ${
          single ? 'grid-cols-1' : 'grid-cols-2'
        } ${className}`}
        role="img"
        aria-label={alt}
        data-visual-kind="composite"
      >
        {layers.map((layer, index) => (
          <figure
            key={layer.product_id}
            data-layer-role={layer.slot}
            className={`relative flex min-h-0 flex-col overflow-hidden bg-paper-deep ${
              fillLast && index === layers.length - 1 ? 'col-span-2' : ''
            }`}
          >
            <ResilientImage
              src={layer.image_url}
              alt=""
              productId={layer.product_id}
              decorative
              layerSlot={layer.slot}
              className="absolute inset-0 size-full object-contain p-2"
            />
            <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 bg-paper/80 px-2 py-0.5 text-center text-[0.625rem] font-medium tracking-[0.14em] text-ink-600 uppercase backdrop-blur-sm">
              {roleLabel(layer.slot)}
            </figcaption>
          </figure>
        ))}
      </div>
    )
  }

  // `grid`, or a composite the backend could not fill. Still every real product
  // image, just arranged side by side rather than layered.
  return (
    <div
      className={`grid size-full grid-cols-2 gap-0.5 bg-paper-deep ${className}`}
      role="img"
      aria-label={alt}
      data-visual-kind="grid"
    >
      {raw.items.map((item) => (
        <ResilientImage
          key={item.product_id}
          src={item.image_url}
          alt=""
          productId={item.product_id}
          decorative
          gridSlot={item.slot}
          className="size-full bg-paper-deep object-cover mix-blend-multiply"
        />
      ))}
    </div>
  )
}

/**
 * A quiet marker for illustrative artwork.
 *
 * The backend flags its own generated imagery with `demo_imagery`. This renders
 * that as a single small label rather than a paragraph, because the alternative -
 * letting a shopper read a rendered garment as a photograph of a real product -
 * is the one thing the imagery must not do.
 */
export function DemoImageryTag({ demo }: { demo: boolean }) {
  if (!demo) return null
  return (
    <span
      data-demo-imagery="true"
      className="pointer-events-none absolute right-3 bottom-3 bg-paper/85 px-2 py-1 text-[0.625rem] font-medium tracking-[0.16em] text-ink-700 uppercase backdrop-blur-sm"
    >
      Demo catalog
    </span>
  )
}
