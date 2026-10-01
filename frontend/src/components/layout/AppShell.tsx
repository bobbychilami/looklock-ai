/**
 * The product shell: a quiet masthead and a hairline footer.
 *
 * The try-on proof of concept is deliberately absent from the shopper-facing
 * navigation. It is an API demonstration, not part of the LOOKLOCK journey, and
 * putting it in the nav invites the demo to be read as the product.
 */

import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-ink-200 bg-paper/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-5">
          <Link
            to="/"
            className="font-display text-xl tracking-tight text-ink-950"
            aria-label="LOOKLOCK home"
          >
            LOOKLOCK
          </Link>

          <nav className="flex items-center gap-6">
            <Link
              to="/create"
              className="text-sm tracking-wide text-ink-700 uppercase transition-colors hover:text-ink-950"
            >
              Create my look
            </Link>
            <span className="hidden text-xs tracking-[0.18em] text-ink-500 uppercase sm:inline">
              YouCam API Hackathon 2026
            </span>
          </nav>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-ink-200 bg-paper-deep">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-8 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between">
          <p>
            LOOKLOCK AI &middot; a demo experience. Products, brands and prices are fictional.
          </p>
          <p>
            All YouCam calls are made from the backend. No credentials reach the browser.{' '}
            <Link to="/dev/status" className="underline underline-offset-2">
              System status
            </Link>
          </p>
        </div>
      </footer>
    </div>
  )
}
