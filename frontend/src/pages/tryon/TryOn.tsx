/**
 * Try-on progress.
 *
 * The backend exposes internal phase names (`uploading_reference_image` and so
 * on). Those are an implementation detail of how we talk to a vendor, so they
 * are translated here into the four things the shopper is actually waiting for.
 * The raw phase is still sent to the data attribute, because when a run fails at
 * 2am the useful question is which step of the pipeline broke.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { getProductTryOnJob, startProductTryOn } from '@/api/looklock'
import type { ProductTryOnStatusResponse, TryOnPhase } from '@/api/types'
import { AppShell } from '@/components/layout/AppShell'
import { ProductImage } from '@/components/product/ProductTile'
import { Button } from '@/components/ui/Button'
import { formatInr } from '@/lib/format'
import { useLookSession } from '@/state/looklock'

/** Ordered steps the UI shows, each mapped from one or more backend phases. */
const STEPS: { phase: TryOnPhase; label: string; detail: string }[] = [
  { phase: 'queued', label: 'Starting up', detail: 'Your request is queued.' },
  {
    phase: 'uploading_source_image',
    label: 'Sending your photo',
    detail: 'Uploading your photo to the try-on service.',
  },
  {
    phase: 'uploading_reference_image',
    label: 'Sending the garment',
    detail: 'Uploading this garment from the LOOKLOCK catalogue.',
  },
  { phase: 'submitting_task', label: 'Building your look', detail: 'Starting the try-on.' },
  {
    phase: 'polling_task',
    label: 'Almost there',
    detail: 'Generating the image. This usually takes under a minute.',
  },
]

const POLL_INTERVAL_MS = 1500
/** Stop polling well before this so a wedged backend cannot spin forever. */
const MAX_POLL_MS = 120000

export default function TryOn() {
  const { productId } = useParams<{ productId: string }>()
  const navigate = useNavigate()
  const { recommendation, photo, consent } = useLookSession()

  const [status, setStatus] = useState<ProductTryOnStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(true)

  const pollRef = useRef<{ controller: AbortController; timer: number } | null>(null)

  /**
   * The garment the try-on will use as its reference.
   *
   * The route param is still a `product_id` and the request is still a single
   * product, exactly as before - this is the same VTO path, reading the same
   * catalogue data from a session that now holds normalised looks.
   */
  const hero = recommendation?.looks
    .flatMap((look) => look.items)
    .find((item) => item.product_id === productId)

  /**
   * The try-on can only run for a piece the vendor can accept. An accessory has no
   * garment reference, and a piece whose only reference is a remote/CDN image is
   * one we hold back until we can guarantee the service accepts it - the look
   * detail page disables the button for exactly these, and a direct visit to this
   * route must not start a billable job the UI has already refused to offer.
   */
  const heroTryonReady = hero ? hero.is_tryon_capable && !hero.tryon_uses_remote_image : false

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearTimeout(pollRef.current.timer)
      pollRef.current.controller.abort()
      pollRef.current = null
    }
  }, [])

  useEffect(() => stopPolling, [stopPolling])

  useEffect(() => {
    if (!productId || !photo || !consent) return
    if (!heroTryonReady) return

    const controller = new AbortController()

    // The start is deferred by a tick. React StrictMode mounts, runs this effect,
    // immediately tears it down and runs it again; the teardown aborts `controller`.
    // Deferring means that first, throwaway pass cancels a *pending* start instead
    // of a live one, so we neither fire a second billable try-on nor leave the very
    // first request aborted (which parked the UI on "queued" forever).
    const startTimer = window.setTimeout(() => {
      startProductTryOn(productId, photo, controller.signal)
        .then((accepted) => {
          setStarting(false)
          poll(accepted.job_id, 0)
        })
        .catch((cause: unknown) => {
          if (cause instanceof DOMException && cause.name === 'AbortError') return
          setStarting(false)
          setError(cause instanceof Error ? cause.message : 'Could not start the try-on.')
        })
    }, 0)

    /** Recursive on purpose: each poll schedules the next, so there is exactly
     *  one outstanding request and unmounting can cancel it cleanly. */
    function poll(jobId: string, elapsed: number): void {
      if (controller.signal.aborted || elapsed > MAX_POLL_MS) return
      getProductTryOnJob(jobId, controller.signal)
        .then((body) => {
          setStatus(body)
          if (body.phase === 'completed' && body.result_url) {
            navigate(`/result/${body.job_id}`, { replace: true })
            return
          }
          if (body.phase === 'failed') {
            setError(body.error ?? 'The try-on failed.')
            return
          }
          const timer = window.setTimeout(
            () => poll(jobId, elapsed + POLL_INTERVAL_MS),
            POLL_INTERVAL_MS,
          )
          pollRef.current = { controller, timer }
        })
        .catch((cause: unknown) => {
          if (cause instanceof DOMException && cause.name === 'AbortError') return
          setError(cause instanceof Error ? cause.message : 'Lost contact with the backend.')
        })
    }

    return () => {
      window.clearTimeout(startTimer)
      controller.abort()
    }
  }, [productId, photo, consent, heroTryonReady, navigate])

  // Refuse rather than silently failing later: without a photo or consent there
  // is nothing legal to send, and a 422 from the backend would be a worse
  // experience than saying so.
  if (!photo || !consent) return <Navigate to="/looks" replace />
  if (!hero) return <Navigate to="/looks" replace />
  if (!heroTryonReady) return <Navigate to="/looks" replace />

  const activePhase = status?.phase ?? 'queued'
  const activeIndex = STEPS.findIndex((step) => step.phase === activePhase)
  const progress = activeIndex === -1 ? 0 : Math.round((activeIndex / (STEPS.length - 1)) * 100)

  return (
    <AppShell>
      <div className="mx-auto max-w-xl px-6 py-20">
        <div className="flex flex-col items-center gap-4 text-center">
          <p className="eyebrow">Virtual try-on</p>
          <h1 className="text-title text-ink-950">Trying on {hero.name}</h1>
          <p className="text-sm text-ink-700">
            {formatInr(hero.price_inr)} &middot; {hero.color}
          </p>
        </div>

        <div className="mx-auto mt-8 w-full max-w-xs overflow-hidden rounded-editorial border border-ink-200 bg-white">
          <ProductImage product={hero} className="aspect-4/5 w-full" />
        </div>

        {error ? (
          <div className="mt-10 flex flex-col gap-4 border-l-2 border-accent-600 bg-accent-100/40 px-5 py-4">
            <p className="text-sm text-accent-700">{error}</p>
            <Button variant="secondary" onClick={() => navigate('/looks')}>
              Back to your looks
            </Button>
          </div>
        ) : (
          <>
            {/* Progress bar. `aria-valuenow` keeps it announced for screen
                readers without needing a live region for the whole list. */}
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              aria-label="Try-on progress"
              className="mt-10 h-1 w-full bg-ink-200"
            >
              <div
                className="h-full bg-accent-500 transition-all duration-500"
                style={{ width: `${Math.max(progress, 3)}%` }}
              />
            </div>

            <ol className="mt-8 flex flex-col gap-4">
              {STEPS.map((step, index) => {
                const done = activeIndex > index || activePhase === 'completed'
                const current = activeIndex === index
                return (
                  <li
                    key={step.phase}
                    data-phase={activePhase}
                    className="flex items-start gap-3"
                  >
                    <span
                      aria-hidden
                      className={`mt-1 size-2 shrink-0 rounded-full ${
                        done ? 'bg-accent-500' : current ? 'bg-accent-500/40' : 'bg-ink-200'
                      }`}
                    />
                    <span className="flex flex-col">
                      <span
                        className={`text-sm ${current || done ? 'font-medium text-ink-950' : 'text-ink-500'}`}
                      >
                        {step.label}
                      </span>
                      {current && (
                        <span className="text-xs text-ink-700">{step.detail}</span>
                      )}
                    </span>
                  </li>
                )
              })}
            </ol>

            <p className="mt-10 text-center text-xs text-ink-500">
              {starting ? 'Starting...' : 'This can take up to a minute.'}{' '}
              Powered by YouCam AI Clothes Virtual Try-On V4.0.
            </p>
          </>
        )}
      </div>
    </AppShell>
  )
}
