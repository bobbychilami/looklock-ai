import type { ButtonHTMLAttributes } from 'react'

/** Small helper for the `variant` prop pattern used across the primitives. */
export type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const VARIANT_CLASSES: Record<Variant, string> = {
  // Ink rather than a brand colour: the accent belongs to the garments, so the
  // primary action reads as "the quiet confident choice" not "a bright button".
  primary:
    'bg-ink-950 text-paper hover:bg-ink-900 disabled:bg-ink-300 disabled:text-ink-500',
  secondary:
    'bg-transparent text-ink-900 border border-ink-300 hover:border-ink-900 hover:bg-paper-deep',
  ghost: 'bg-transparent text-ink-700 hover:bg-ink-100',
  danger: 'bg-accent-600 text-white hover:bg-accent-700',
}

const SIZE_CLASSES = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-7 py-3.5 text-sm',
} as const

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: keyof typeof SIZE_CLASSES
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-editorial font-medium tracking-wide transition-colors disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...props}
    />
  )
}
