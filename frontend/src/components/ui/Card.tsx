import type { HTMLAttributes } from 'react'

export type CardVariant = 'default' | 'muted' | 'accent'

const VARIANT_CLASSES: Record<CardVariant, string> = {
  default: 'card',
  muted: 'card border-ink-200 bg-paper-deep',
  accent: 'card border-accent-500/30 bg-accent-100/40',
}

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant
}

export function Card({ variant = 'default', className = '', ...props }: CardProps) {
  return <div className={`${VARIANT_CLASSES[variant]} ${className}`} {...props} />
}

export function CardHeader({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`flex flex-col gap-1.5 p-6 ${className}`} {...props} />
}

export function CardTitle({ className = '', ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={`font-display text-lg text-ink-950 ${className}`} {...props} />
}

export function CardBody({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`p-6 pt-0 text-sm text-ink-700 ${className}`} {...props} />
}
