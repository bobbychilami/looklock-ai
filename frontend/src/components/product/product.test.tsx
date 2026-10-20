/**
 * Component tests for the product surfaces.
 *
 * These are the tests that would have caught the bug that motivated the look
 * model: a card that pictured one garment while describing five. So the visual
 * assertions are deliberately strict about *which* image is on screen, not just
 * that some image is.
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { toLookView, toProductView } from '@/api/normalize'
import { LookCard } from '@/components/product/LookCard'
import { LookVisual } from '@/components/product/LookVisual'
import { ProductTile } from '@/components/product/ProductTile'
import { formatInr } from '@/lib/format'
import {
  gridLookFixture,
  lookOneFixture,
  shoppableLookFixture,
  styledLookFixture,
} from '@/test/fixtures'

function renderInRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('LookVisual', () => {
  it('uses a styled photograph as one image when the provider supplies one', () => {
    const look = toLookView(styledLookFixture, 25000, formatInr)
    renderInRouter(<LookVisual look={look} />)

    const frame = document.querySelector('[data-visual-kind="complete_look"]')
    expect(frame).toBeInstanceOf(HTMLImageElement)
    expect(frame).toHaveAttribute('src', '/api/v1/catalog/items/upper-ivory-sherwani/styled')
    expect(frame).toHaveAttribute('alt', 'Ivory Wedding Look, styled by Kapoor & Sons')
  })

  it('layers every piece of the look when there is no styled photograph', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    renderInRouter(<LookVisual look={look} />)

    const frame = document.querySelector('[data-visual-kind="composite"]')
    expect(frame).not.toBeNull()

    // All five products are present as layers, each tagged with its own role.
    const slots = Array.from(document.querySelectorAll('img[data-layer-slot]')).map((node) =>
      node.getAttribute('data-layer-slot'),
    )
    expect(slots).toEqual(['top', 'bottom', 'outerwear', 'footwear', 'accessory'])
  })

  it('carries the backend alt text so the composed outfit is announced once', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    renderInRouter(<LookVisual look={look} />)

    // A stack of five images must not be read as five unrelated products, so
    // only the top layer keeps a description and the rest are hidden.
    expect(
      document.querySelector('[data-visual-kind="composite"]'),
    ).toHaveAttribute('aria-label', 'Ceremonial Bandhgala composed from 5 product images')

    const described = screen
      .getAllByRole('img')
      .filter((node) => node.getAttribute('aria-label'))
    expect(described).toHaveLength(1)
  })

  it('falls back to a plain grid when the backend cannot illustrate the look', () => {
    const look = toLookView(gridLookFixture, 25000, formatInr)
    renderInRouter(<LookVisual look={look} />)

    expect(document.querySelector('[data-visual-kind="grid"]')).not.toBeNull()
    // Every piece still gets its real photograph, just side by side.
    expect(document.querySelectorAll('img[data-grid-slot]')).toHaveLength(5)
  })

  it('falls back to the grid when a composite has no layers to draw', () => {
    // An empty `layers` array must not render a blank frame.
    const empty = {
      ...lookOneFixture,
      visual: { ...lookOneFixture.visual, layers: [] },
    }
    renderInRouter(<LookVisual look={toLookView(empty, 25000, formatInr)} />)
    expect(document.querySelector('[data-visual-kind="grid"]')).not.toBeNull()
  })

  it('falls back to the grid when a complete_look has no image to show', () => {
    const missing = {
      ...styledLookFixture,
      visual: { ...styledLookFixture.visual, image_url: null },
    }
    renderInRouter(<LookVisual look={toLookView(missing, 25000, formatInr)} />)
    expect(document.querySelector('[data-visual-kind="grid"]')).not.toBeNull()
  })

  it('labels illustrative artwork and says nothing when imagery is real', () => {
    const demo = toLookView(lookOneFixture, 25000, formatInr)
    const { unmount } = renderInRouter(<LookCard look={demo} />)
    expect(screen.getByText('Demo catalog')).toBeInTheDocument()
    unmount()

    const real = toLookView(styledLookFixture, 25000, formatInr)
    renderInRouter(<LookCard look={real} />)
    expect(screen.queryByText('Demo catalog')).not.toBeInTheDocument()
  })
})

describe('LookCard', () => {
  it('is titled by the backend look name, not by one product', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    renderInRouter(<LookCard look={look} />)

    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('Ceremonial Bandhgala')
    // The old card headed this with the first product, which described one of
    // five garments and implied the rest were optional.
    expect(screen.queryByRole('heading', { name: 'Ivory Bandhgala' })).not.toBeInTheDocument()
    expect(screen.getByText('Bandhgala + 4 more pieces')).toBeInTheDocument()
  })

  it('does not fall back to the first product image while a look visual exists', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    renderInRouter(<LookCard look={look} />)

    // The bandhgala is still *in* the composite, as a layer. What must not
    // happen is it standing alone as the picture of the whole outfit.
    expect(document.querySelector('[data-visual-kind="composite"]')).not.toBeNull()
    expect(document.querySelectorAll('img')).toHaveLength(5)
    expect(screen.getByRole('heading', { level: 3 }).textContent).not.toBe(
      lookOneFixture.items[0].name,
    )
  })

  it('shows the total price and the match the backend computed', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    renderInRouter(<LookCard look={look} />)

    expect(screen.getByText('₹24,800')).toBeInTheDocument()
    expect(screen.getByText('79% match')).toBeInTheDocument()
  })

  it('states how far a look is over budget, with the shopper’s own budget', () => {
    const look = toLookView(lookOneFixture, 8000, formatInr)
    renderInRouter(<LookCard look={look} />)

    const row = document.querySelector('[data-budget-state="over"]')
    expect(row).toHaveTextContent('Over your ₹8,000 budget by ₹16,800')
  })

  it('shows no budget warning when the look fits', () => {
    const look = toLookView(styledLookFixture, 25000, formatInr)
    renderInRouter(<LookCard look={look} />)
    expect(document.querySelector('[data-budget-state="over"]')).toBeNull()
  })

  it('links to the look detail route using the backend look id', async () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    renderInRouter(<LookCard look={look} />)

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/look/look-1')
    await userEvent.click(link)
    expect(link).toHaveAttribute('href', '/look/look-1')
  })
})

describe('ProductTile', () => {
  it('takes the garment role from the backend slot', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    render(
      <ul>
        {look.productViews.map((view) => (
          <ProductTile key={view.item.product_id} view={view} />
        ))}
      </ul>,
    )

    // All five roles are rendered, including outerwear, which the old copy did
    // not have a word for.
    expect(screen.getByText('Top')).toBeInTheDocument()
    expect(screen.getByText('Bottom')).toBeInTheDocument()
    expect(screen.getByText('Outerwear')).toBeInTheDocument()
    expect(screen.getByText('Footwear')).toBeInTheDocument()
    expect(screen.getByText('Accessory')).toBeInTheDocument()
  })

  it('keeps outerwear in dressing order, above the top it covers', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    render(
      <ul>
        {look.productViews.map((view) => (
          <ProductTile key={view.item.product_id} view={view} />
        ))}
      </ul>,
    )

    const roles = screen
      .getAllByText(/^(Top|Bottom|Outerwear|Footwear|Accessory)$/)
      .map((node) => node.textContent)
    expect(roles).toEqual(['Top', 'Bottom', 'Outerwear', 'Footwear', 'Accessory'])
  })

  it('names the retailer only when the backend supplied one', () => {
    const shoppable = toLookView(shoppableLookFixture, 8000, formatInr)
    const { unmount } = render(
      <ul>
        <ProductTile view={shoppable.productViews[0]} />
      </ul>,
    )
    // "Retailer: Kapoor & Sons" is the attribution; the shop link repeats the
    // name on purpose, so both are scoped rather than matched loosely.
    expect(screen.getByText('Retailer:')).toBeInTheDocument()
    expect(screen.getByText('Kapoor & Sons')).toBeInTheDocument()
    unmount()

    const demo = toLookView(lookOneFixture, 25000, formatInr)
    render(
      <ul>
        <ProductTile view={demo.productViews[0]} />
      </ul>,
    )
    expect(screen.queryByText(/^Retailer:/)).not.toBeInTheDocument()
  })

  it('links out only when there is a verified purchase URL', () => {
    const shoppable = toLookView(shoppableLookFixture, 8000, formatInr)
    render(
      <ul>
        <ProductTile view={shoppable.productViews[0]} />
      </ul>,
    )

    const link = screen.getByRole('link', { name: /Shop at Kapoor & Sons/ })
    expect(link).toHaveAttribute('href', 'https://retailer.example.com/p/ivory-silk-sherwani')
  })

  it('never renders a shop link for a demo product with no listing', () => {
    // This is the case that matters most today: the demo catalogue has no
    // retailer at all, so a dead "Shop now" would be a fabricated affordance.
    const demo = toLookView(lookOneFixture, 25000, formatInr)
    render(
      <ul>
        <ProductTile view={demo.productViews[0]} />
      </ul>,
    )

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('Demo')).toBeInTheDocument()
  })

  it('says a listing is missing rather than omitting a product that is still shown', () => {
    const noUrl = toProductView(
      { ...shoppableLookFixture.items[0], purchase_url: null, can_shop: false },
      formatInr,
    )
    render(
      <ul>
        <ProductTile view={noUrl} />
      </ul>,
    )

    // The garment, its role and its price are all still real and worth showing.
    expect(screen.getByText('Ivory Silk Sherwani')).toBeInTheDocument()
    expect(screen.getByText('₹3,800')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('No link yet')).toBeInTheDocument()
    expect(screen.getByText('No verified listing URL')).toBeInTheDocument()
  })

  it('labels a sold-out listing but keeps its link', () => {
    // The fixture's mojari is deliberately out of stock.
    const view = toProductView(shoppableLookFixture.items[2], formatInr)
    render(
      <ul>
        <ProductTile view={view} />
      </ul>,
    )

    expect(screen.getByText('Out of stock')).toBeInTheDocument()
    // Suppressing the link would hide the authoritative answer, which is the one
    // page that knows about restock and alternatives.
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', view.shopUrl)
  })

  it('says nothing about stock when the source did not report it', () => {
    const unknown = toProductView(
      { ...shoppableLookFixture.items[0], availability: 'unknown' },
      formatInr,
    )
    render(
      <ul>
        <ProductTile view={unknown} />
      </ul>,
    )

    // Absence of information is not permission to imply a guarantee.
    expect(screen.queryByText('Out of stock')).not.toBeInTheDocument()
    expect(screen.queryByText('In stock')).not.toBeInTheDocument()
  })

  it('opens retailer links in a new tab without leaking the opener', () => {
    const shoppable = toLookView(shoppableLookFixture, 8000, formatInr)
    render(
      <ul>
        <ProductTile view={shoppable.productViews[0]} />
      </ul>,
    )

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('target', '_blank')
    // Both tokens, not just one: `noopener` hides window.opener and
    // `noreferrer` withholds the referrer.
    const rel = link.getAttribute('rel') ?? ''
    expect(rel).toContain('noopener')
    expect(rel).toContain('noreferrer')
  })

  it('renders each garment inside a list item tagged with its slot', () => {
    const look = toLookView(lookOneFixture, 25000, formatInr)
    render(
      <ul>
        {look.productViews.map((view) => (
          <ProductTile key={view.item.product_id} view={view} />
        ))}
      </ul>,
    )

    const list = screen.getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(5)
    expect(list.querySelector('[data-slot="outerwear"]')).not.toBeNull()
  })
})
