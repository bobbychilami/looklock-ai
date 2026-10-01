/**
 * Display formatting for catalogue values.
 *
 * Prices are whole rupees in the domain model and only ever compared as
 * integers; the only place a rupee string should be produced is here, so the
 * UI cannot disagree with itself about how a price is written.
 */

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

export function formatInr(amount: number): string {
  return inrFormatter.format(amount)
}

/** Compact form for tight spots like a card corner, e.g. `₹2.4k`. */
export function formatInrCompact(amount: number): string {
  if (amount < 1000) return formatInr(amount)
  if (amount < 100000) return `₹${Math.round(amount / 1000)}k`
  return `₹${Math.round(amount / 1000)}k`
}

const SLOT_LABELS: Record<string, string> = {
  top: 'Top',
  bottom: 'Bottom',
  footwear: 'Footwear',
  accessory: 'Accessory',
}

/** Human label for an outfit slot. Falls back to the raw value from the API. */
export function slotLabel(slot: string): string {
  return SLOT_LABELS[slot] ?? slot
}

/** Percentage string for a 0..1 score component. */
export function formatScore(value: number): string {
  return `${Math.round(value * 100)}%`
}
