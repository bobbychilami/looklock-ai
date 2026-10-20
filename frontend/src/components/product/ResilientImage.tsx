/**
 * Product artwork with a JPEG fallback.
 *
 * A provider listing's image is loaded from its own CDN, which keeps the bytes on
 * the licensed host and off this backend. Some of those thumbnails are WebP, and a
 * browser that cannot decode WebP simply fails the load. When that happens this
 * swaps in the backend's `/image.jpg` route once, so a broken picture becomes a
 * working JPEG instead of an empty box. A healthy load never reaches the fallback.
 */

import { useState } from 'react'

import { assetUrl, config } from '@/config/env'

/** The backend route that re-fetches and normalises a product image. */
function jpegFallbackUrl(productId: string): string {
  const path = `${config.apiPrefix}/catalog/items/${encodeURIComponent(productId)}/image.jpg`
  return assetUrl(path) ?? path
}

type Stage = 'primary' | 'fallback' | 'failed'

interface ResilientImageProps {
  src: string | null | undefined
  alt: string
  /** The product whose backend JPEG fallback should be tried if `src` fails. */
  productId?: string | null
  className?: string
  loading?: 'lazy' | 'eager'
  /** A layer inside a captioned composite: no text alternative of its own. */
  decorative?: boolean
  /** Mirrored onto `data-layer-slot` for the composite's ordering contract. */
  layerSlot?: string
  /** Mirrored onto `data-grid-slot` for the flat grid's contract. */
  gridSlot?: string
}

export function ResilientImage({
  src,
  alt,
  productId,
  className = '',
  loading = 'lazy',
  decorative = false,
  layerSlot,
  gridSlot,
}: ResilientImageProps) {
  const primary = assetUrl(src)
  const fallback = productId ? jpegFallbackUrl(productId) : undefined

  // The stage is remembered *with* the primary it belongs to, so a new product
  // starts clean without an effect. `recorded` is the primary the stage describes.
  const [failure, setFailure] = useState<{ recorded: string | undefined; stage: Stage }>({
    recorded: primary,
    stage: 'primary',
  })
  const stage: Stage = failure.recorded === primary ? failure.stage : 'primary'

  const resolved = stage === 'primary' ? primary : stage === 'fallback' ? fallback : undefined

  if (!resolved) {
    // Nothing left to try. A shape-holding box beats a broken-image glyph, and the
    // grid keeps the dimensions the caller asked for.
    return <span aria-hidden className={`block bg-paper-deep ${className}`} />
  }

  return (
    <img
      src={resolved}
      alt={decorative ? '' : alt}
      aria-hidden={decorative || undefined}
      data-layer-slot={layerSlot}
      data-grid-slot={gridSlot}
      className={className}
      loading={loading}
      onError={() =>
        setFailure((previous) => {
          const current = previous.recorded === primary ? previous.stage : 'primary'
          return {
            recorded: primary,
            stage: current === 'primary' && fallback ? 'fallback' : 'failed',
          }
        })
      }
    />
  )
}
