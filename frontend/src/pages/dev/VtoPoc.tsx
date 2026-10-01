/**
 * Virtual try-on proof of concept.
 *
 * This page is deliberately isolated from the main LOOKLOCK flow: it exists to
 * prove that one documented YouCam operation works end to end, and to make the
 * vendor round trip visible instead of hiding it behind a spinner.
 *
 * What it shows, in order:
 *   1. both images being uploaded (two File API round trips),
 *   2. the cloth-v4 task being created,
 *   3. the task being polled until YouCam reports success or error,
 *   4. the single result image, which is a temporary link.
 *
 * What it does not do: store anything, refresh an expired result, or pretend
 * this is the finished product experience.
 */

import { useEffect, useRef, useState } from 'react'

import { getTryOnJob, getTryOnOptions, startTryOn } from '@/api/looklock'
import { ApiRequestError } from '@/api/client'
import type { TryOnOptionsResponse, TryOnPhase, TryOnStatusResponse } from '@/api/types'
import { AppShell } from '@/components/layout/AppShell'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { FilePicker } from '@/components/ui/FilePicker'

/** Fallback step order. The backend's `/options` response is preferred. */
const FALLBACK_PHASES: TryOnPhase[] = [
  'queued',
  'uploading_source_image',
  'uploading_reference_image',
  'submitting_task',
  'polling_task',
  'completed',
]

const STEP_LABELS: Record<TryOnPhase, string> = {
  queued: 'Request accepted',
  uploading_source_image: 'Uploading your photo',
  uploading_reference_image: 'Uploading the garment photo',
  submitting_task: 'Creating the YouCam task',
  polling_task: 'Waiting for YouCam to render',
  completed: 'Result ready',
  failed: 'Failed',
}

const MULTI_PERSON_LABELS: Record<string, string> = {
  off: 'Off - use the largest person',
  normal: 'Normal - reject a similar-sized second person',
  strict: 'Strict - reject any second person',
}

const POLL_INTERVAL_MS = 1000
/** Hard stop so a wedged backend cannot poll forever. */
const MAX_POLLS = 300

type RunState =
  | { kind: 'idle' }
  | { kind: 'starting' }
  | { kind: 'running'; jobId: string; status: TryOnStatusResponse | null }
  | { kind: 'done'; status: TryOnStatusResponse }
  | { kind: 'error'; message: string; errorCode?: string; jobId?: string }

export default function VtoPoc() {
  const [options, setOptions] = useState<TryOnOptionsResponse | null>(null)
  const [optionsError, setOptionsError] = useState<string | null>(null)

  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [garmentFile, setGarmentFile] = useState<File | null>(null)
  const [garmentCategory, setGarmentCategory] = useState('auto')
  const [multiPerson, setMultiPerson] = useState('off')

  const [run, setRun] = useState<RunState>({ kind: 'idle' })
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getTryOnOptions(controller.signal)
      .then(setOptions)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setOptionsError(error instanceof Error ? error.message : 'Unexpected error')
      })
    return () => controller.abort()
  }, [])

  // Abort any in-flight polling if the user navigates away mid-run.
  useEffect(() => () => abortRef.current?.abort(), [])

  const phases = options?.phases ?? FALLBACK_PHASES
  const busy = run.kind === 'starting' || run.kind === 'running'
  const status = run.kind === 'running' ? run.status : run.kind === 'done' ? run.status : null

  async function handleSubmit() {
    if (!sourceFile || !garmentFile) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const form = new FormData()
    form.append('source_image', sourceFile)
    form.append('reference_image', garmentFile)
    form.append('garment_category', garmentCategory)
    form.append('filter_multi_person', multiPerson)

    setRun({ kind: 'starting' })

    let jobId: string
    try {
      const accepted = await startTryOn(form, controller.signal)
      jobId = accepted.job_id
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      setRun({ kind: 'error', ...toErrorState(error) })
      return
    }

    setRun({ kind: 'running', jobId, status: null })
    await pollUntilDone(jobId, controller)
  }

  async function pollUntilDone(jobId: string, controller: AbortController) {
    for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
      await sleep(POLL_INTERVAL_MS, controller.signal)

      try {
        const next = await getTryOnJob(jobId, controller.signal)
        if (next.phase === 'completed' || next.phase === 'failed') {
          setRun(
            next.phase === 'completed'
              ? { kind: 'done', status: next }
              : {
                  kind: 'error',
                  message: next.error ?? 'YouCam could not produce a result.',
                  errorCode: next.error_code ?? undefined,
                  jobId,
                },
          )
          return
        }
        setRun({ kind: 'running', jobId, status: next })
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setRun({ kind: 'error', ...toErrorState(error), jobId })
        return
      }
    }

    setRun({
      kind: 'error',
      message:
        'Stopped polling after 5 minutes. YouCam keeps working upstream, but we do not retain the task id, so this result cannot be recovered here.',
      errorCode: 'polling_gave_up',
      jobId,
    })
  }

  function handleCancel() {
    abortRef.current?.abort()
    setRun({ kind: 'idle' })
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-8">
        <section className="flex flex-col gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-ink-950">
            Virtual try-on proof of concept
          </h1>
          <p className="max-w-2xl text-ink-700">
            One real run through <code className="text-xs">AI Clothes Virtual Try-On V4.0</code>: two
            image uploads, an asynchronous task, and the single result image. Every vendor call is
            made by the backend, so no YouCam credential exists in this page.
          </p>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Inputs</CardTitle>
          </CardHeader>
          <CardBody>
            <div className="grid gap-6 sm:grid-cols-2">
              <FilePicker
                label="Your photo"
                hint="Single person, facing forward, standing. JPEG or PNG."
                file={sourceFile}
                disabled={busy}
                onChange={setSourceFile}
              />
              <FilePicker
                label="Garment photo"
                hint="Front-facing shot of one garment. For full body, the whole outfit must be visible."
                file={garmentFile}
                disabled={busy}
                onChange={setGarmentFile}
              />
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <Select
                label="Garment category"
                value={garmentCategory}
                disabled={busy}
                onChange={setGarmentCategory}
                options={(options?.garment_categories ?? ['auto']).map((value) => ({
                  value,
                  label: value.replace(/_/g, ' '),
                }))}
              />
              <Select
                label="Multiple people"
                value={multiPerson}
                disabled={busy}
                onChange={setMultiPerson}
                options={(options?.multi_person_filters ?? ['off']).map((value) => ({
                  value,
                  label: MULTI_PERSON_LABELS[value] ?? value,
                }))}
              />
            </div>

            {options && (
              <p className="mt-4 text-xs text-ink-500">
                {options.youcam_endpoint} · max {Math.round(options.max_image_bytes / 1024 / 1024)} MB
                per image
              </p>
            )}
            {optionsError && (
              <p className="mt-4 text-xs text-red-700">
                Could not load the documented options: {optionsError}. Using built-in defaults.
              </p>
            )}

            <div className="mt-6 flex items-center gap-3">
              <Button
                onClick={handleSubmit}
                disabled={busy || !sourceFile || !garmentFile}
                className="min-w-40"
              >
                {run.kind === 'starting' ? 'Uploading...' : busy ? 'Running...' : 'Run try-on'}
              </Button>
              {busy && (
                <Button variant="secondary" onClick={handleCancel}>
                  Cancel
                </Button>
              )}
              {!busy && (sourceFile === null || garmentFile === null) && (
                <span className="text-xs text-ink-500">Choose both images to continue.</span>
              )}
            </div>
          </CardBody>
        </Card>

        {run.kind !== 'idle' && <ProgressCard run={run} phases={phases} status={status} />}

        <Card variant="muted">
          <CardHeader>
            <CardTitle>What this page does not do</CardTitle>
          </CardHeader>
          <CardBody>
            <ul className="list-disc pl-5">
              <li>Nothing is saved. No image, no task id, no history.</li>
              <li>
                The result link is a presigned URL that YouCam expires in about two hours. It cannot
                be refreshed from here.
              </li>
              <li>
                There is no product catalog yet, so both images come from your device. The garment
                image is the one V4.0 always requires.
              </li>
              <li>
                Unit cost for V4.0 is not published; V2.0 and V3.0 are documented as 2 units each.
              </li>
            </ul>
            {options && options.notes.length > 0 && (
              <ul className="mt-4 list-disc pl-5 text-xs text-ink-500">
                {options.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </AppShell>
  )
}

function ProgressCard({
  run,
  phases,
  status,
}: {
  run: RunState
  phases: TryOnPhase[]
  status: TryOnStatusResponse | null
}) {
  if (run.kind === 'error') {
    return (
      <Card variant="accent">
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-3">
            Try-on failed
            {run.errorCode && <Badge tone="error">{run.errorCode}</Badge>}
          </CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-ink-900">{run.message}</p>
          {run.jobId && <p className="mt-2 text-xs text-ink-500">Job id: {run.jobId}</p>}
        </CardBody>
      </Card>
    )
  }

  if (run.kind === 'starting') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Starting</CardTitle>
        </CardHeader>
        <CardBody>Sending both images to the backend...</CardBody>
      </Card>
    )
  }

  const current = status?.phase ?? 'queued'
  const currentIndex = Math.max(phases.indexOf(current), 0)
  const failed = current === 'failed'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3">
          Progress
          <Badge tone={failed ? 'error' : current === 'completed' ? 'ok' : 'neutral'}>
            {current.replace(/_/g, ' ')}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardBody>
        <ol className="flex flex-col gap-2">
          {phases.map((phase, index) => {
            const done = !failed && index < currentIndex
            const active = phase === current
            return (
              <li key={phase} className="flex items-center gap-3">
                <span
                  aria-hidden
                  className={[
                    'size-2.5 shrink-0 rounded-full',
                    done ? 'bg-emerald-500' : active ? 'bg-brand-500' : 'bg-ink-300',
                  ].join(' ')}
                />
                <span
                  className={[
                    'text-sm',
                    active ? 'font-medium text-ink-950' : 'text-ink-700',
                    done ? 'text-ink-500' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {STEP_LABELS[phase]}
                  {phase === 'polling_task' && status?.youcam_task_status && (
                    <span className="ml-2 text-xs text-ink-500">
                      YouCam says: {status.youcam_task_status}
                    </span>
                  )}
                </span>
              </li>
            )
          })}
        </ol>

        <dl className="mt-5 grid gap-3 sm:grid-cols-2">
          <Row label="Job id" value={run.kind === 'running' ? run.jobId : (status?.job_id ?? '')} />
          <Row label="YouCam task id" value={status?.youcam_task_id ?? 'not created yet'} />
        </dl>

        {status?.result_url && <ResultPanel status={status} />}
      </CardBody>
    </Card>
  )
}

function ResultPanel({ status }: { status: TryOnStatusResponse }) {
  return (
    <div className="mt-6 flex flex-col gap-4 border-t border-ink-100 pt-6">
      <div className="flex items-center gap-3">
        <h4 className="text-sm font-semibold text-ink-950">Result</h4>
        <Badge tone="warn">link expires in ~{status.result_url_expires_in_hours}h</Badge>
      </div>

      {status.result_url && (
        <img
          src={status.result_url}
          alt="Virtual try-on result"
          className="max-h-[32rem] w-full rounded-xl border border-ink-100 object-contain"
        />
      )}

      <details className="text-xs">
        <summary className="cursor-pointer text-ink-500">Result URL</summary>
        <a
          href={status.result_url ?? '#'}
          target="_blank"
          rel="noreferrer"
          className="mt-2 block break-all text-ink-700 underline underline-offset-2"
        >
          {status.result_url}
        </a>
      </details>

      <ul className="list-disc pl-5 text-xs text-ink-500">
        {status.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  )
}

function Select({
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  disabled: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium tracking-wide text-ink-500 uppercase">{label}</span>
      <select
        value={value}
        disabled={disabled}
        className="rounded-xl border border-ink-300 bg-white px-3 py-2 text-sm text-ink-900 disabled:cursor-not-allowed disabled:opacity-60"
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs tracking-wide text-ink-500 uppercase">{label}</dt>
      <dd className="truncate font-mono text-xs text-ink-900">{value}</dd>
    </div>
  )
}

function toErrorState(error: unknown): { message: string; errorCode?: string } {
  if (error instanceof ApiRequestError) {
    return {
      message: error.detail,
      ...(error.errorCode ? { errorCode: error.errorCode } : {}),
    }
  }
  return { message: error instanceof Error ? error.message : 'Unexpected error' }
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    function onAbort() {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal.addEventListener('abort', onAbort, { once: true })
  })
}