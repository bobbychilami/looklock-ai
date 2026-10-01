/**
 * Landing page.
 *
 * The claim is deliberately the one the product can actually back: you see the
 * outfit before you buy it. Everything below the fold is a three-step summary
 * of the real flow rather than marketing copy, so nothing on this page is a
 * promise the app cannot keep.
 */

import { Link } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'

const STEPS = [
  {
    n: '01',
    title: 'Tell us the occasion',
    body: 'A wedding, an interview, a night out. Context is what separates an outfit from a pile of clothes.',
  },
  {
    n: '02',
    title: 'Say what you like, and what you will spend',
    body: 'A style axis and a real budget. Every recommendation is ranked against both, and the maths is shown to you.',
  },
  {
    n: '03',
    title: 'See it on you, then shop it',
    body: 'Put the top on your own photo, then walk away with a full price breakdown if it works.',
  },
]

export default function Home() {
  return (
    <AppShell>
      {/* Hero */}
      <section className="border-b border-ink-200 bg-paper">
        <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-[1.1fr_0.9fr] lg:py-28">
          <div className="flex flex-col justify-center gap-7">
            <p className="eyebrow">AI styling, visual proof</p>
            <h1 className="text-display text-ink-950">
              Know how you&rsquo;ll look
              <br />
              <span className="text-accent-600">before you buy.</span>
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-ink-700">
              Tell LOOKLOCK where you are going and what you like. We&rsquo;ll build three complete
              outfits from a real catalogue, show you exactly why each one earned its rank,
              and let you try the top on your own photo before spending anything.
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <Link
                to="/create"
                className="inline-flex items-center justify-center rounded-editorial bg-ink-950 px-7 py-3.5 text-sm font-medium tracking-wide text-paper transition-colors hover:bg-ink-900"
              >
                Create my look
              </Link>
              <span className="text-sm text-ink-500">Takes about a minute.</span>
            </div>
          </div>

          {/* Look preview: the four slots an outfit is built from. */}
          <div className="relative mx-auto w-full max-w-sm">
            <div className="grid grid-cols-2 gap-3">
              <PreviewPanel label="Top" tone="bg-accent-100" />
              <PreviewPanel label="Bottom" tone="bg-paper-deep" offset />
              <PreviewPanel label="Footwear" tone="bg-paper-deep" />
              <PreviewPanel label="Accessory" tone="bg-accent-100" offset />
            </div>
            <p className="mt-4 text-center text-xs tracking-wide text-ink-500 uppercase">
              Every look is scored, not guessed
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-b border-ink-200 bg-paper-deep">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <p className="eyebrow">How it works</p>
          <h2 className="mt-3 text-title text-ink-950">
            Three looks, and the reasoning behind each
          </h2>

          <ol className="mt-12 grid gap-10 md:grid-cols-3">
            {STEPS.map((step) => (
              <li key={step.n} className="flex flex-col gap-3">
                <span className="font-display text-3xl text-accent-500">{step.n}</span>
                <h3 className="font-display text-lg text-ink-950">{step.title}</h3>
                <p className="text-sm leading-relaxed text-ink-700">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* What powers it, and what it cannot do */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid gap-10 lg:grid-cols-2">
          <div className="flex flex-col gap-4">
            <p className="eyebrow">Powers the visual step</p>
            <h2 className="text-title text-ink-950">AI Clothes Virtual Try-On V4.0</h2>
            <p className="text-sm leading-relaxed text-ink-700">
              The try-on itself runs on YouCam&rsquo;s AI Clothes Virtual Try-On V4.0, which
              generates a new image of the garment worn on your photo. LOOKLOCK handles the
              styling, the ranking and the shopping decision; YouCam handles the pixels.
            </p>
          </div>

          <div className="flex flex-col gap-4">
            <p className="eyebrow">Straight about the limits</p>
            <ul className="flex flex-col gap-3 text-sm leading-relaxed text-ink-700">
              <li className="border-l-2 border-accent-500 pl-4">
                <strong className="font-medium text-ink-950">The catalogue is a demo.</strong>{' '}
                All products are fictional, with illustrative prices and no retailer behind them.
                Nothing here is for sale.
              </li>
              <li className="border-l-2 border-accent-500 pl-4">
                <strong className="font-medium text-ink-950">
                  Your photo is processed by a third party.
                </strong>{' '}
                It is sent to the try-on service to generate the image and is not retained by
                LOOKLOCK. The result link expires after about two hours.
              </li>
              <li className="border-l-2 border-accent-500 pl-4">
                <strong className="font-medium text-ink-950">Accuracy varies.</strong> Generative
                try-on gets fit and drape approximately right. Treat it as a strong hint, not a
                photograph of a real fitting room.
              </li>
            </ul>
          </div>
        </div>
      </section>
    </AppShell>
  )
}

/** One placeholder panel. Real garments appear once the catalogue is fetched. */
function PreviewPanel({
  label,
  tone,
  offset = false,
}: {
  label: string
  tone: string
  offset?: boolean
}) {
  return (
    <div className={`flex aspect-4/5 items-end p-3 ${tone} ${offset ? 'translate-y-4' : ''}`}>
      <span className="text-[0.6875rem] font-medium tracking-[0.18em] text-ink-500 uppercase">
        {label}
      </span>
    </div>
  )
}
