/**
 * API contract and privacy tests.
 *
 * The point of these is the *outgoing* direction: what the browser sends. A
 * frontend can be correct about everything it displays and still leak a secret,
 * or quietly send a field the backend does not accept, and neither shows up in a
 * rendering test.
 *
 * `fetch` is stubbed rather than the API module, so the assertions are about the
 * real request the real client code builds - URL, method, headers and body.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { postRecommendations, startProductTryOn } from '@/api/looklock'
import { config } from '@/config/env'
import {
  weddingOverBudgetFixture,
  weddingWithinBudgetFixture,
} from '@/test/fixtures'

/** Every URL the browser asked for during a test. */
const requestedUrls: string[] = []

/**
 * Replies with `body` for any request. `body` defaults to an empty object, which
 * is enough for tests that only care about the outgoing request - but not for
 * calls that normalise the response, so those pass a real fixture.
 */
function stubFetch(body: unknown = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      requestedUrls.push(String(input))
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }),
  )
}

/** The request the client most recently built. */
function lastRequest() {
  const calls = (fetchMock.mock.calls ?? []) as [string, RequestInit][]
  const call = calls.at(-1)
  if (!call) throw new Error('no fetch call was made')
  const [url, init] = call
  return { url, init }
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  requestedUrls.length = 0
  stubFetch()
  fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('recommendations request', () => {
  it('sends only the three answers the backend accepts', async () => {
    stubFetch(weddingOverBudgetFixture)
    fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>

    await postRecommendations(
      { occasion: 'Wedding', style: 'Classic', budget_inr: 8000 },
      new AbortController().signal,
    )

    const { url, init } = lastRequest()
    expect(url).toBe(`${config.apiBaseUrl}${config.apiPrefix}/recommendations`)
    expect(init.method).toBe('POST')

    const body = JSON.parse(String(init.body)) as Record<string, unknown>
    // Exactly three keys. The photo, the answers' history and anything else a
    // future edit might add would all be rejected by the request schema, and a
    // rejection here would surface as a confusing 422 to the shopper.
    expect(Object.keys(body).sort()).toEqual(['budget_inr', 'occasion', 'style'])
    expect(body).toEqual({ occasion: 'Wedding', style: 'Classic', budget_inr: 8000 })
  })

  it('does not put a credential in the query string, where it would land in logs', async () => {
    stubFetch(weddingOverBudgetFixture)
    fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>

    await postRecommendations(
      { occasion: 'Party', style: 'Bold', budget_inr: 5000 },
      new AbortController().signal,
    )

    const { url } = lastRequest()
    expect(url).not.toMatch(/[?&](key|token|secret|api_key)=/i)
    // No query string at all: the payload is a body.
    expect(url.includes('?')).toBe(false)
  })

  it('returns a normalised view rather than the raw wire shape', async () => {
    stubFetch(weddingOverBudgetFixture)
    fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>

    const view = await postRecommendations(
      { occasion: 'Wedding', style: 'Classic', budget_inr: 8000 },
      new AbortController().signal,
    )

    // Proof the normalisation ran: the view has derived fields the wire shape
    // does not have, and its `look` holds the original untouched for the score.
    expect(view.budget.status).toBe('none_affordable')
    expect(view.looks[0].name).toBe('Ceremonial Bandhgala')
    expect(view.looks[0].look.score.total).toBeCloseTo(0.7863)
  })

  it('surfaces the backend budget state instead of inventing one', async () => {
    stubFetch(weddingWithinBudgetFixture)
    fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>

    const view = await postRecommendations(
      { occasion: 'Wedding', style: 'Classic', budget_inr: 25000 },
      new AbortController().signal,
    )

    expect(view.budget.status).toBe('met')
    // The engine's notice lives on the budget view, and is `null` here - there
    // is nothing to warn about, so no sentence should be shown at all.
    expect(view.budget.notice).toBeNull()
  })
})

describe('try-on request', () => {
  /**
   * The photo is the most sensitive thing this app handles, so the shape of the
   * upload is asserted explicitly: the file under the name the backend expects,
   * and nothing else riding along.
   */
  it('uploads the photo and product id as multipart form data', async () => {
    stubFetch({ job_id: 'job-1', status: 'accepted' })
    fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>

    const photo = new File(['pretend-bytes'], 'me.jpg', { type: 'image/jpeg' })
    await startProductTryOn('upper-ivory-bandhgala', photo, new AbortController().signal)

    const { url, init } = lastRequest()
    expect(url).toBe(`${config.apiBaseUrl}${config.apiPrefix}/tryon`)
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)

    const form = init.body as FormData
    expect(form.get('source_image')).toBeInstanceOf(File)
    expect((form.get('source_image') as File).name).toBe('me.jpg')
    expect(form.get('product_id')).toBe('upper-ivory-bandhgala')
  })

  it('sends only the two documented fields, not the whole session', async () => {
    stubFetch({ job_id: 'job-1', status: 'accepted' })
    fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>

    const photo = new File(['x'], 'me.jpg', { type: 'image/jpeg' })
    await startProductTryOn('upper-ivory-bandhgala', photo, new AbortController().signal)

    const form = lastRequest().init.body as FormData
    // Occasion, style and budget stay in the browser. The try-on service has no
    // use for them and no business receiving them.
    expect([...form.keys()].sort()).toEqual(['product_id', 'source_image'])
  })
})

describe('no secret is exposed to the browser bundle', () => {
  it('config exposes a base URL and nothing that looks like a credential', () => {
    // `config` is the entire runtime configuration available to the bundle. If a
    // key were ever added here it would ship to every visitor, so the shape of
    // this object is itself worth asserting.
    expect(Object.keys(config).sort()).toEqual(['apiBaseUrl', 'apiPrefix'])
    expect(JSON.stringify(config)).not.toMatch(/key|secret|token|password/i)
  })

  it('only ever calls the LOOKLOCK backend, never a try-on vendor directly', async () => {
    stubFetch(weddingOverBudgetFixture)
    fetchMock = vi.mocked(fetch) as unknown as ReturnType<typeof vi.fn>

    await postRecommendations(
      { occasion: 'Casual', style: 'Minimal', budget_inr: 2000 },
      new AbortController().signal,
    )
    await startProductTryOn(
      'upper-ivory-bandhgala',
      new File(['x'], 'me.jpg', { type: 'image/jpeg' }),
      new AbortController().signal,
    )

    expect(requestedUrls).toHaveLength(2)
    for (const url of requestedUrls) {
      // A direct vendor call from the browser would expose the key and put a
      // third party in the middle of the shopper's photo.
      expect(url.startsWith(`${config.apiBaseUrl}${config.apiPrefix}`)).toBe(true)
      expect(url).not.toMatch(/youcam|ycam|alicdn|youcamapi/i)
    }
  })
})
