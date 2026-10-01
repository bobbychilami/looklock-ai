/**
 * Onboarding: occasion, style, budget, photo.
 *
 * One linear wizard rather than four routes. The steps share a single piece of
 * session state and each one commits its answer immediately, so going back and
 * forth never loses anything and the form stays honest about what is still
 * missing.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Occasion, Style } from '@/api/types'
import { AppShell } from '@/components/layout/AppShell'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { FilePicker } from '@/components/ui/FilePicker'
import { formatInr } from '@/lib/format'
import {
  MAX_BUDGET_INR,
  MIN_BUDGET_INR,
  OPEN_BUDGET_CEILING_INR,
  useLookSession,
} from '@/state/looklock'

const STEPS = ['Occasion', 'Style', 'Budget', 'Photo'] as const

/** Label hints for the vocabulary, keyed by the backend's exact literals. */
const OCCASION_HINTS: Record<Occasion, string> = {
  Wedding: 'Guest, bride or groom-side',
  'Date Night': 'Dinner, drinks, something memorable',
  Interview: 'Conservative, well-fitted, quiet',
  Party: 'Confident, you want to be looked at',
  Casual: 'Everyday, errands, meeting friends',
}

const STYLE_HINTS: Record<Style, string> = {
  Classic: 'Timeless, tailored, unremarkable in the best way',
  Modern: 'Clean lines, current cuts, minimal fuss',
  Bold: 'Colour, print, statement accessories',
  Minimal: 'Almost nothing, but exactly right',
}

export default function Onboarding() {
  const navigate = useNavigate()
  const {
    occasion,
    style,
    budgetInr,
    photo,
    consent,
    photoPreviewUrl,
    catalogue,
    loadCatalogue,
    setAnswers,
    buildLooks,
    pending,
    error,
  } = useLookSession()

  const [step, setStep] = useState(0)
  const [customBudget, setCustomBudget] = useState('')

  useEffect(() => {
    // The options are fetched, not hard-coded, so the wizard can never offer an
    // answer the backend request schema would reject.
    const controller = new AbortController()
    void loadCatalogue(controller.signal).catch(() => {
      /* the step remains usable from the fallback lists below */
    })
    return () => controller.abort()
  }, [loadCatalogue])

  const occasions = catalogue?.occasions ?? (Object.keys(OCCASION_HINTS) as Occasion[])
  const styles = catalogue?.styles ?? (Object.keys(STYLE_HINTS) as Style[])
  const presets = catalogue?.budget_presets_inr ?? [2000, 5000, 8000, 15000, 25000]

  const canAdvance =
    step === 0 ? Boolean(occasion) : step === 1 ? Boolean(style) : step === 2 ? Boolean(budgetInr) : Boolean(photo && consent)

  async function handleSubmit() {
    const recommendation = await buildLooks()
    if (recommendation) navigate('/looks')
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="eyebrow">Step {step + 1} of {STEPS.length}</p>
        <h1 className="mt-3 text-title text-ink-950">{headingFor(step)}</h1>
        <p className="mt-2 text-sm text-ink-700">{subheadingFor(step)}</p>

        {/* Progress */}
        <ol className="mt-8 flex items-center gap-2" aria-label="Progress">
          {STEPS.map((label, index) => (
            <li key={label} className="flex flex-1 items-center gap-2">
              <span
                className={`h-1 w-full ${index <= step ? 'bg-accent-500' : 'bg-ink-200'}`}
                aria-hidden
              />
              <span
                className={`text-[0.6875rem] tracking-wide uppercase ${
                  index === step ? 'text-ink-950' : 'text-ink-500'
                }`}
              >
                {label}
              </span>
            </li>
          ))}
        </ol>

        <div className="mt-10">
          {step === 0 && (
            <ChoiceGrid<Occasion>
              options={occasions}
              value={occasion}
              onChange={(value) => setAnswers({ occasion: value })}
              hintFor={(value) => OCCASION_HINTS[value]}
            />
          )}

          {step === 1 && (
            <ChoiceGrid<Style>
              options={styles}
              value={style}
              onChange={(value) => setAnswers({ style: value })}
              hintFor={(value) => STYLE_HINTS[value]}
            />
          )}

          {step === 2 && (
            <BudgetStep
              presets={presets}
              value={budgetInr}
              customBudget={customBudget}
              onPreset={(value) => {
                setAnswers({ budgetInr: value })
                setCustomBudget('')
              }}
              onCustomChange={(text) => {
                setCustomBudget(text)
                const parsed = Number.parseInt(text, 10)
                setAnswers({
                  budgetInr:
                    Number.isNaN(parsed) || parsed < MIN_BUDGET_INR || parsed > MAX_BUDGET_INR
                      ? null
                      : parsed,
                })
              }}
            />
          )}

          {step === 3 && (
            <PhotoStep
              photo={photo}
              previewUrl={photoPreviewUrl}
              consent={consent}
              onPhotoChange={(file) => setAnswers({ photo: file, consent: false })}
              onConsentChange={(value) => setAnswers({ consent: value })}
            />
          )}
        </div>

        {error && (
          <div className="mt-6 border-l-2 border-accent-600 bg-accent-100/40 px-4 py-3 text-sm text-accent-700">
            {error}
          </div>
        )}

        {/* Controls */}
        <div className="mt-10 flex items-center justify-between gap-4">
          <Button
            variant="ghost"
            onClick={() => setStep((current) => Math.max(0, current - 1))}
            disabled={step === 0 || pending}
          >
            Back
          </Button>

          {step < STEPS.length - 1 ? (
            <Button onClick={() => setStep((current) => current + 1)} disabled={!canAdvance}>
              Continue
            </Button>
          ) : (
            <Button onClick={handleSubmit} disabled={!canAdvance || pending} size="lg">
              {pending ? 'Building your looks...' : 'Show my looks'}
            </Button>
          )}
        </div>
      </div>
    </AppShell>
  )
}

function headingFor(step: number): string {
  return ['Where are you dressing for?', 'How do you want to look?', 'What is your budget?', 'Add a photo of yourself'][
    step
  ]
}

function subheadingFor(step: number): string {
  return [
    'This is the single strongest signal in the ranking.',
    'We rank against this axis, but the occasion still wins ties.',
    'A total for the whole outfit, not per item. We will not quietly go over.',
    'Used only to generate the try-on image. You can skip the try-on and still shop the looks.',
  ][step]
}

/** Radio-style grid, so keyboard and screen-reader users get real semantics. */
function ChoiceGrid<T extends string>({
  options,
  value,
  onChange,
  hintFor,
}: {
  options: readonly T[]
  value: T | null
  onChange: (value: T) => void
  hintFor: (value: T) => string | undefined
}) {
  return (
    <div role="radiogroup" className="grid gap-3 sm:grid-cols-2">
      {options.map((option) => {
        const selected = value === option
        const hint = hintFor(option)
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option)}
            className={`flex flex-col gap-1.5 border p-4 text-left transition-colors ${
              selected
                ? 'border-accent-600 bg-accent-100/40'
                : 'border-ink-200 bg-white hover:border-ink-500'
            }`}
          >
            <span className="font-display text-lg text-ink-950">{option}</span>
            {hint && <span className="text-xs text-ink-700">{hint}</span>}
          </button>
        )
      })}
    </div>
  )
}

function BudgetStep({
  presets,
  value,
  customBudget,
  onPreset,
  onCustomChange,
}: {
  presets: number[]
  value: number | null
  customBudget: string
  onPreset: (value: number) => void
  onCustomChange: (text: string) => void
}) {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-3 sm:grid-cols-3">
        {presets.map((preset) => {
          const selected = value === preset
          const isOpenTop = preset === presets[presets.length - 1]
          return (
            <button
              key={preset}
              type="button"
              aria-pressed={selected}
              onClick={() => onPreset(preset)}
              className={`border px-4 py-3 text-center transition-colors ${
                selected
                  ? 'border-accent-600 bg-accent-100/40'
                  : 'border-ink-200 bg-white hover:border-ink-500'
              }`}
            >
              <span className="block font-display text-lg text-ink-950">
                {isOpenTop ? `${formatInr(preset)}+` : formatInr(preset)}
              </span>
            </button>
          )
        })}
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="custom-budget" className="eyebrow">
          Or set your own
        </label>
        <div className="flex items-center gap-3">
          <span className="text-ink-500">₹</span>
          <input
            id="custom-budget"
            type="number"
            inputMode="numeric"
            min={MIN_BUDGET_INR}
            max={MAX_BUDGET_INR}
            value={customBudget}
            onChange={(event) => onCustomChange(event.target.value)}
            placeholder={`${MIN_BUDGET_INR} to ${MAX_BUDGET_INR.toLocaleString('en-IN')}`}
            className="w-full border border-ink-200 bg-white px-3 py-2.5 text-sm text-ink-950 placeholder:text-ink-300"
          />
        </div>
        <p className="text-xs text-ink-500">
          Between {formatInr(MIN_BUDGET_INR)} and {formatInr(MAX_BUDGET_INR)}. The top preset is
          treated as up to {formatInr(OPEN_BUDGET_CEILING_INR)}.
        </p>
      </div>
    </div>
  )
}

function PhotoStep({
  photo,
  previewUrl,
  consent,
  onPhotoChange,
  onConsentChange,
}: {
  photo: File | null
  previewUrl: string | null
  consent: boolean
  onPhotoChange: (file: File | null) => void
  onConsentChange: (value: boolean) => void
}) {
  return (
    <div className="flex flex-col gap-6">
      {/* A full-width preview reads better here than the small square the
          generic picker uses, and this is the image people are nervous about
          sharing - they should be able to see exactly what they selected. */}
      {previewUrl ? (
        <div className="relative mx-auto w-full max-w-xs overflow-hidden rounded-editorial border border-ink-200">
          <img src={previewUrl} alt="Your selected photo" className="aspect-3/4 w-full object-cover" />
        </div>
      ) : (
        <div className="flex aspect-3/4 w-full max-w-xs items-center justify-center rounded-editorial border border-dashed border-ink-300 bg-paper-deep">
          <span className="text-xs tracking-wide text-ink-500 uppercase">No photo selected</span>
        </div>
      )}

      <FilePicker
        label="Photo"
        hint="JPEG or PNG, up to 10 MB. A clear, front-facing photo works best."
        file={photo}
        onChange={onPhotoChange}
      />

      <label className="flex cursor-pointer items-start gap-3 border border-ink-200 bg-paper-deep p-4">
        <input
          type="checkbox"
          checked={consent}
          onChange={(event) => onConsentChange(event.target.checked)}
          className="mt-0.5 size-4 accent-ink-950"
        />
        <span className="text-sm leading-relaxed text-ink-700">
          I understand this photo is sent to the virtual try-on service to generate an image of
          me wearing the garment. LOOKLOCK does not store it, and the generated result link
          expires after about two hours.
          {!consent && photo && <Badge tone="warn" className="mt-2">Required to try on</Badge>}
        </span>
      </label>
    </div>
  )
}
