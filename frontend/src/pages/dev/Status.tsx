/**
 * System status, kept off the shopper-facing flow under `/dev`.
 *
 * This is the diagnostic view: backend liveness, whether the YouCam credential
 * is present, and the integration surface with its open items. It is the page
 * to open when the try-on returns 503, so it deliberately reports the *state*
 * of the configuration and never the value.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getCatalogueSummary, getHealth, getIntegrationStatus, getReadiness } from '@/api/looklock'
import type { HealthResponse, IntegrationStatusResponse, ReadyResponse } from '@/api/types'
import { AppShell } from '@/components/layout/AppShell'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | {
      status: 'ready'
      health: HealthResponse
      readiness: ReadyResponse
      integration: IntegrationStatusResponse
    }

export default function Status() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()

    Promise.all([
      getHealth(controller.signal),
      getReadiness(controller.signal),
      getIntegrationStatus(controller.signal),
    ])
      .then(([health, readiness, integration]) => {
        setState({ status: 'ready', health, readiness, integration })
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unexpected error',
        })
      })

    return () => controller.abort()
  }, [])

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-6 py-16">
        <header className="flex flex-col gap-3">
          <p className="eyebrow">Developer tools</p>
          <h1 className="text-title text-ink-950">System status</h1>
          <p className="text-sm text-ink-700">
            Diagnostics for the backend and the YouCam integration. Not part of the shopper
            journey.
          </p>
        </header>

        <div className="mt-10 flex flex-col gap-6">
          {state.status === 'loading' && (
            <Card>
              <CardBody>Checking backend connection...</CardBody>
            </Card>
          )}

          {state.status === 'error' && (
            <Card variant="accent">
              <CardHeader>
                <CardTitle>Backend unreachable</CardTitle>
              </CardHeader>
              <CardBody>{state.message}</CardBody>
            </Card>
          )}

          {state.status === 'ready' && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-3">
                    Backend status
                    <Badge tone={state.readiness.youcam_configured ? 'ok' : 'warn'}>
                      {state.readiness.youcam_configured
                        ? 'YouCam configured'
                        : 'YouCam not configured'}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardBody>
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <Row label="Service" value={state.health.service} />
                    <Row label="Version" value={state.health.version} />
                    <Row label="Environment" value={state.health.environment} />
                    <Row label="Readiness" value={state.readiness.detail} />
                  </dl>
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Catalogue</CardTitle>
                </CardHeader>
                <CardBody>
                  <CatalogueCard />
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>YouCam integration surface</CardTitle>
                </CardHeader>
                <CardBody>
                  <ul className="flex flex-col gap-4">
                    {state.integration.features.map((feature) => (
                      <li key={feature.name} className="flex flex-col gap-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-ink-900">{feature.name}</span>
                          <Badge tone={feature.implemented ? 'ok' : 'neutral'}>
                            {feature.implemented ? 'wired' : 'not built'}
                          </Badge>
                          <code className="text-xs text-ink-500">{feature.youcam_endpoint}</code>
                        </div>
                        <p className="text-sm text-ink-700">{feature.notes}</p>
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Virtual try-on proof of concept</CardTitle>
                </CardHeader>
                <CardBody>
                  <p className="max-w-2xl">
                    The raw integration harness: upload a photo of the person and a photo of the
                    garment, watch both uploads, the task submission and the polling, then see the
                    single result image.
                  </p>
                  <div className="mt-4">
                    <Link to="/dev/vto">
                      <Button variant="secondary">Open the try-on proof of concept</Button>
                    </Link>
                  </div>
                  <p className="mt-4 max-w-2xl text-xs text-ink-500">
                    The product uses the same runner through <code>/api/v1/tryon</code>, with the
                    reference garment resolved from the catalogue instead of uploaded.
                  </p>
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Known gaps</CardTitle>
                </CardHeader>
                <CardBody>
                  <ul className="list-disc pl-5">
                    {state.integration.open_items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs tracking-wide text-ink-500 uppercase">{label}</dt>
      <dd className="text-sm text-ink-900">{value}</dd>
    </div>
  )
}

/** Catalogue shape, so a bad seed or a missing asset is visible immediately. */
function CatalogueCard() {
  const [summary, setSummary] = useState<{
    product_count: number
    counts_by_slot: Record<string, number>
    notice: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getCatalogueSummary(controller.signal)
      .then(setSummary)
      .catch((cause: unknown) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : 'Could not load the catalogue.')
      })
    return () => controller.abort()
  }, [])

  if (error) return <p className="text-sm text-accent-700">{error}</p>
  if (!summary) return <p className="text-sm text-ink-500">Loading catalogue...</p>

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">{summary.product_count} products</Badge>
        {Object.entries(summary.counts_by_slot).map(([slot, count]) => (
          <Badge key={slot} tone="neutral">
            {count} {slot}
          </Badge>
        ))}
      </div>
      <p className="text-xs text-ink-500">{summary.notice}</p>
    </div>
  )
}
