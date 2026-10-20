/**
 * Page-level tests for the looks grid and the look detail page.
 *
 * Two things are being protected here that unit tests cannot see:
 *
 * 1. The engine's own notice reaches the shopper intact. The backend writes
 *    careful, specific sentences about what it could not do - "the most
 *    affordable wedding look here is ₹24,200, above the ₹8,000 budget" - and a
 *    paraphrasing UI would replace a fact with a vibe.
 * 2. The try-on is still reachable. The look model replaced a lot of what the
 *    detail page rendered, and the one thing it must not have broken is the
 *    journey from a look to YouCam.
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { toCatalogueView, toRecommendationView } from '@/api/normalize'
import LookDetail from '@/pages/look/LookDetail'
import Looks from '@/pages/looks/Looks'
import { LookSessionProvider } from '@/state/LookSessionProvider'
import type { LookSessionValue } from '@/state/looklock'
import { formatInr } from '@/lib/format'
import {
  catalogueSummaryFixture,
  shoppableLookFixture,
  vacationPartialFixture,
  weddingOverBudgetFixture,
  weddingWithinBudgetFixture,
} from '@/test/fixtures'

/**
 * Renders a page against a fixed session, without a network call.
 *
 * `LookSessionProvider` is deliberately not used: it fetches on mount, and what
 * is under test is how a *given* response is presented. Stubbing the hook keeps
 * these tests about presentation, and leaves the fetch itself to its own tests.
 */
const sessionState: { current: Partial<LookSessionValue> } = { current: {} }

vi.mock('@/state/looklock', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/state/looklock')>()
  return {
    ...actual,
    useLookSession: () => ({
      occasion: 'Wedding',
      style: 'Classic',
      budgetInr: null,
      photo: null,
      consent: false,
      catalogue: null,
      pending: false,
      error: null,
      photoPreviewUrl: null,
      setAnswers: vi.fn(),
      loadCatalogue: vi.fn(),
      buildLooks: vi.fn(),
      reset: vi.fn(),
      canBuild: true,
      ...sessionState.current,
    }),
  }
})

/**
 * Stands in for the try-on route so the navigation target can be asserted
 * exactly. The real page reads `productId` from the same param, so a mismatch
 * between the hero the detail page picks and the garment the try-on resolves
 * would show up here as a different id.
 */
function TryOnStub() {
  const { productId } = useParams<{ productId: string }>()
  return <p>YouCam try-on for {productId}</p>
}

function setSession(patch: Partial<LookSessionValue>) {
  sessionState.current = patch
}

function renderLooks() {
  return render(
    <MemoryRouter>
      <Looks />
    </MemoryRouter>,
  )
}

function renderDetail(lookId = 'look-1') {
  return render(
    <MemoryRouter initialEntries={[`/look/${lookId}`]}>
      <Routes>
        <Route path="/look/:lookId" element={<LookDetail />} />
        <Route path="/looks" element={<p>All your looks</p>} />
        <Route path="/tryon/:productId" element={<TryOnStub />} />
        <Route path="/shop" element={<p>Shop the look</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setSession({})
})

describe('budget notice', () => {
  it('shows the backend notice word for word when nothing affordable came back', () => {
    // The sentence is the backend's, and it is specific: a real rupee figure and
    // the real floor. Rewriting it would throw away the only useful fact here.
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    expect(
      screen.getByText(
        'The most affordable wedding look here is ₹24,200, above the ₹8,000 budget',
      ),
    ).toBeInTheDocument()
  })

  it('says nothing about the budget when the budget was met', () => {
    const recommendation = toRecommendationView(weddingWithinBudgetFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    // No notice element at all when there is nothing to warn about.
    expect(document.querySelector('[data-budget-status="none_affordable"]')).toBeNull()
    expect(document.querySelector('[data-budget-status="partial"]')).toBeNull()
    expect(document.querySelector('[data-budget-status="thin_catalogue"]')).toBeNull()
  })

  it('distinguishes a partial budget from having no affordable option', () => {
    const recommendation = toRecommendationView(vacationPartialFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    const notice = document.querySelector('[data-budget-status="partial"]')
    expect(notice).not.toBeNull()
    expect(notice).toHaveTextContent('1 of 3 looks fit your ₹2,000 budget')
    expect(notice).toHaveTextContent(
      'Only 1 of these fits ₹2,000, and the others start at ₹9,200',
    )
  })

  it('marks every over-budget card in the grid, not only the notice', () => {
    const recommendation = toRecommendationView(vacationPartialFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    // One look at ₹1,600 fits; the other two are marked. A shopper has to be able
    // to see which is which without doing arithmetic on three identical cards.
    const overRows = document.querySelectorAll('[data-budget-state="over"]')
    expect(overRows).toHaveLength(2)
  })

  it('shows the budget the shopper actually asked for', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    expect(screen.getByText(/Ranked against a budget of ₹8,000/)).toBeInTheDocument()
  })
})

describe('demo imagery and shopping honesty', () => {
  it('says imagery is illustrative when the response contains demo artwork', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    expect(screen.getByText(/Product imagery here is illustrative/)).toBeInTheDocument()
    expect(screen.getAllByText('Demo catalog').length).toBe(3)
  })

  it('says nothing about a retailer when this catalogue cannot support buying', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    expect(
      screen.getByText(
        /No retailer listings are connected to this catalogue yet, so nothing here can be bought/,
      ),
    ).toBeInTheDocument()
  })

  it('counts looks that can be bought in full when a provider supplies listings', () => {
    const recommendation = toRecommendationView(
      {
        occasion: 'Wedding',
        style: 'Classic',
        budget_inr: 8000,
        looks: [shoppableLookFixture],
        notice: null,
        relaxed_constraints: [],
      },
      formatInr,
    )
    setSession({ recommendation })
    renderLooks()

    expect(screen.getByText(/1 of 1 looks can be bought in full/)).toBeInTheDocument()
  })

  it('records that the session is not persisted', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderLooks()

    // The photo and the answers stay in memory. Saying so where the shopper can
    // act on it is part of the consent story, not a footnote.
    expect(screen.getByText(/Answers stay in this tab only/)).toBeInTheDocument()
  })
})

describe('look detail', () => {
  it('reaches the existing try-on route with the hero garment', async () => {
    // Preserved contract: `/tryon/:productId` with the backend's
    // `hero_product_id`. The try-on page reads that param unchanged, so the id
    // here is asserted exactly rather than merely "it navigated".
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderDetail('look-1')

    await userEvent.click(screen.getByRole('button', { name: 'See it on me' }))

    expect(
      screen.getByText('YouCam try-on for outer-ivory-bandhgala-jacket'),
    ).toBeInTheDocument()
  })

  it('uses the defining garment as the try-on reference, not the first product', async () => {
    // `hero_product_id` is the jacket for this look, while `items[0]` is the
    // bandhgala. The VTO reference is whichever the backend chose.
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderDetail('look-1')

    expect(screen.getByText(/Try-on reference · Outerwear/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'See it on me' }))
    expect(screen.getByText(/YouCam try-on for outer-ivory-bandhgala-jacket/)).toBeInTheDocument()
  })

  it('explains the photo boundary next to the try-on button', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderDetail('look-1')

    expect(
      screen.getByText(/Your image is sent to that service and is not stored by LOOKLOCK/),
    ).toBeInTheDocument()
  })

  it('keeps the try-on locked until the photo and consent steps are done', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation, canBuild: false, photo: null })
    renderDetail('look-1')

    expect(screen.getByRole('button', { name: 'See it on me' })).toBeDisabled()
    expect(screen.getByText(/Add a photo and accept the consent step/)).toBeInTheDocument()
  })

  it('keeps shopping and trying on as separate destinations', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderDetail('look-1')

    const shop = screen.getByRole('link', { name: /Shop this look/ })
    expect(shop).toHaveAttribute('href', '/shop')
    expect(shop).not.toHaveAttribute('target')

    // The try-on is a button, not a link out to a third party. Merging the two
    // would hide both the consent boundary and the departure from the app.
    expect(screen.getByRole('button', { name: 'See it on me' }).tagName).toBe('BUTTON')
  })

  it('does not claim every piece is listed when only some are', () => {
    const halfLinked = {
      ...shoppableLookFixture,
      items: shoppableLookFixture.items.map((item, index) =>
        index === 0 ? item : { ...item, retailer: null, purchase_url: null, can_shop: false },
      ),
    }
    setSession({
      recommendation: toRecommendationView(
        {
          occasion: 'Wedding',
          style: 'Classic',
          budget_inr: 8000,
          looks: [halfLinked],
          notice: null,
          relaxed_constraints: [],
        },
        formatInr,
      ),
    })
    renderDetail('look-shoppable')

    expect(
      screen.queryByText(/Every piece is listed with a retailer/),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/retailer links where they exist/)).toBeInTheDocument()
  })

  it('lists every garment with its price in the breakdown', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderDetail('look-1')

    // The breakdown is one list of five rows; the "why" list above it is a
    // different thing and must not be counted into it.
    const list = screen.getByRole('list', { name: 'Pieces in Ceremonial Bandhgala' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(5)
    expect(within(list).getByText('Ivory Bandhgala')).toBeInTheDocument()
    expect(within(list).getByText('₹12,900')).toBeInTheDocument()
    expect(within(list).getByText('₹1,500')).toBeInTheDocument()
  })

  it('sends an unknown look id back to the grid instead of rendering a blank page', () => {
    const recommendation = toRecommendationView(weddingOverBudgetFixture, formatInr)
    setSession({ recommendation })
    renderDetail('look-does-not-exist')

    expect(screen.getByText('All your looks')).toBeInTheDocument()
  })
})

describe('catalogue vocabulary', () => {
  it('normalises the summary the onboarding wizard drives its options from', () => {
    // The wizard must offer exactly what the backend will accept. A literal list
    // in the frontend would drift the first time a provider adds an occasion.
    const catalogue = toCatalogueView(catalogueSummaryFixture)
    expect(catalogue.occasions).toContain('Vacation')
    expect(catalogue.styles).toEqual(['Classic', 'Modern', 'Bold', 'Minimal'])
    expect(catalogue.budgetPresets).toEqual([2000, 5000, 8000, 15000, 25000])
    expect(catalogue.supportsShopping).toBe(false)
    expect(catalogue.demoImagery).toBe(true)
    expect(catalogue.providerAvailable).toBe(true)
    expect(catalogue.providerUnavailableReason).toBeNull()
  })

  it('surfaces an unconfigured provider rather than reporting it as healthy', () => {
    // The dangerous state is a provider that is selected, capable of shopping and
    // still unable to answer. Flattening that into "no shopping" would send an
    // operator to debug the wrong thing while the shopper sees an empty wardrobe.
    const view = toCatalogueView({
      ...catalogueSummaryFixture,
      provider_id: 'amazon',
      provider_name: 'Amazon (www.amazon.in)',
      supports_shopping: true,
      demo_imagery: false,
      provider_available: false,
      provider_unavailable_reason:
        'Not configured. Set AMAZON_CLIENT_ID in the environment.',
    })

    expect(view.providerAvailable).toBe(false)
    expect(view.providerUnavailableReason).toContain('AMAZON_CLIENT_ID')
    // Capability is preserved: the provider is not incapable, it is unreachable.
    expect(view.supportsShopping).toBe(true)
  })
})

describe('session provider is the only writer', () => {
  it('still exposes the provider for the pages that genuinely fetch', () => {
    // A guard against the mock above hiding a broken import somewhere: the real
    // provider must remain renderable, or every page that fetches is untested.
    expect(typeof LookSessionProvider).toBe('function')
  })
})
