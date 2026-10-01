import type { ReactNode } from 'react'

export type StatusTone = 'ok' | 'warn' | 'error' | 'neutral'

const TONE_CLASSES: Record<StatusTone, string> = {
  ok: 'bg-emerald-100 text-emerald-800 ring-emerald-600/20',
  warn: 'bg-amber-100 text-amber-900 ring-amber-600/20',
  error: 'bg-red-100 text-red-800 ring-red-600/20',
  neutral: 'bg-ink-100 text-ink-700 ring-ink-500/20',
}

export interface BadgeProps {
  tone?: StatusTone
  children: ReactNode
  className?: string
}

export function Badge({ tone = 'neutral', children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${TONE_CLASSES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
