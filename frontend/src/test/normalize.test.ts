/**
 * Normalisation tests.
 *
 * These guard the layer every screen depends on: what a look is called, whether a
 * product can be bought, and which of the four budget situations a response
 * represents. If these drift, every surface drifts with them, so they are tested
 * directly rather than only through a component.
 */

import { describe, expect, it } from 'vitest'

import {
  byDressingOrder,
  roleLabel,
  signatureItem,
  toBudgetView,
  toLookView,
  toProductView,
  toRecommendationView,
} from '@/api/normalize'
import { formatInr } from '@/lib/format'
import {
  gridLookFixture,
  lookOneFixture,
  shoppableLookFixture,
  styledLookFixture,
  vacationPartialFixture,
  weddingOverBudgetFixture,
  weddingWithinBudgetFixture,
} from './fixtures'

describe('roleLabel', () => {
  it('reads the role from the backend slot, never from the product name', () => {
    expect(roleLabel('top')).toBe('Top')
    expect(roleLabel('bottom')).toBe('Bottom')
    expect(roleLabel('outerwear')).toBe('Outerwear')
    expect(roleLabel('footwear')).toBe('Footwear')
    expect(roleLabel('accessory')).toBe('Accessory')
  })

  it('falls back to the raw value for a slot it does not recognise', () => {
    // A future provider may add a slot. It should render rather than disappear.
    expect(roleLabel('headwear')).toBe('headwear')
  })
})

describe('byDressingOrder', () => {
  it('puts outerwear above the top because it is worn over it', () => {
    const order = [...lookOneFixture.items].sort(byDressingOrder).map((item) => item.slot)
    expect(order).toEqual(['top', 'bottom', 'outerwear', 'footwear', 'accessory'])
  })
})

describe('signatureItem', () => {
  it('finds the garment the backend named the look after', () => {
    // "Ceremonial Bandhgala" mentions the bandhgala, so that is the outfit's
    // defining piece - not the jacket that happens to be listed first.
    expect(signatureItem(lookOneFixture)?.product_id).toBe('upper-ivory-bandhgala')
  })

  it('falls back to the hero when the name mentions no known subcategory', () => {
    const look = { ...lookOneFixture, name: 'Something Entirely New' }
    expect(signatureItem(look)?.product_id).toBe(lookOneFixture.hero_product_id)
  })
})

describe('toProductView', () => {
  it('offers a shop link only when the backend says the product can be shopped', () => {
    const demo = toProductView(lookOneFixture.items[0], formatInr)
    expect(demo.shopUrl).toBeNull()
    expect(demo.isDemo).toBe(true)

    const real = toProductView(shoppableLookFixture.items[0], formatInr)
    expect(real.shopUrl).toBe('https://retailer.example.com/p/ivory-silk-sherwani')
    expect(real.retailerName).toBe('Kapoor & Sons')
    expect(real.isDemo).toBe(false)
  })

  it('ignores a URL when can_shop is false, so a half-populated record cannot link out', () => {
    // The backend requires both a retailer and a URL. If a provider ever ships
    // one without the other, `can_shop` is the gate and the URL must not be used.
    const partial = { ...lookOneFixture.items[0], purchase_url: 'https://example.com/p/1' }
    expect(toProductView(partial, formatInr).shopUrl).toBeNull()
  })
})

describe('toLookView', () => {
  it('uses the backend look name rather than the first product name', () => {
    const view = toLookView(lookOneFixture, 25000, formatInr)
    expect(view.name).toBe('Ceremonial Bandhgala')
    // The old card titled this "Ivory Bandhgala", which reads as one garment.
    expect(view.name).not.toBe(lookOneFixture.items[0].name)
  })

  it('summarises the outfit by its signature garment and piece count', () => {
    const view = toLookView(lookOneFixture, 25000, formatInr)
    expect(view.summary).toBe('Bandhgala + 4 more pieces')
    expect(view.pieceCount).toBe(5)
  })

  it('reports the match percentage and total from the backend', () => {
    const view = toLookView(lookOneFixture, 25000, formatInr)
    expect(view.matchPercent).toBe(79)
    expect(view.price).toBe('₹24,800')
  })

  it('marks a look shoppable only when every piece can be bought', () => {
    const real = toLookView(shoppableLookFixture, 8000, formatInr)
    expect(real.isShoppable).toBe(true)
    expect(real.retailerNames).toEqual(['Kapoor & Sons', 'Rajasthan Crafts'])

    const demo = toLookView(lookOneFixture, 25000, formatInr)
    expect(demo.isShoppable).toBe(false)
    expect(demo.shoppableItems).toHaveLength(0)
  })

  it('keeps a partially shoppable look honest rather than calling it buyable', () => {
    const halfLinked = {
      ...shoppableLookFixture,
      items: shoppableLookFixture.items.map((item, index) =>
        index === 0 ? item : { ...item, retailer: null, purchase_url: null, can_shop: false },
      ),
    }
    const view = toLookView(halfLinked, 8000, formatInr)
    expect(view.isShoppable).toBe(false)
    expect(view.shoppableItems).toHaveLength(1)
  })

  it('flags demo imagery from either the visual or the products', () => {
    expect(toLookView(lookOneFixture, 25000, formatInr).hasDemoImagery).toBe(true)
    expect(toLookView(styledLookFixture, 25000, formatInr).hasDemoImagery).toBe(false)
  })
})

describe('toBudgetView', () => {
  it('reports "met" when every look fits', () => {
    expect(toBudgetView(weddingWithinBudgetFixture).status).toBe('met')
  })

  it('reports "none_affordable" when nothing appropriate fits the budget', () => {
    const view = toBudgetView(weddingOverBudgetFixture)
    expect(view.status).toBe('none_affordable')
    expect(view.inBudgetCount).toBe(0)
    expect(view.overBudgetCount).toBe(3)
    expect(view.notice).toBe(
      'The most affordable wedding look here is ₹24,200, above the ₹8,000 budget',
    )
  })

  it('reports "partial" when some looks fit and some do not', () => {
    const view = toBudgetView(vacationPartialFixture)
    expect(view.status).toBe('partial')
    expect(view.inBudgetCount).toBe(1)
    expect(view.overBudgetCount).toBe(2)
  })

  it('reports "thin_catalogue" when fewer than three looks came back', () => {
    // Fewer than three looks is a catalogue shortfall, and that is a different
    // message from "these are over budget" - the shopper needs to know the
    // engine could not even offer a full set.
    const thin = toBudgetView({
      ...weddingWithinBudgetFixture,
      looks: weddingWithinBudgetFixture.looks.slice(0, 1),
    })
    expect(thin.status).toBe('thin_catalogue')
  })

  it('prefers "thin_catalogue" over a budget state when both are true', () => {
    // One look, and it is over budget. The shortfall is the more fundamental
    // problem, so it must not be reported as merely a budget miss.
    const both = toBudgetView({ ...weddingOverBudgetFixture, looks: [lookOneFixture] })
    expect(both.status).toBe('thin_catalogue')
  })

  it('computes how far each look is over budget', () => {
    const view = toLookView(lookOneFixture, 8000, formatInr)
    expect(view.overBudget).toBe(true)
    expect(view.overByInr).toBe(16800)
  })
})

describe('toRecommendationView', () => {
  it('prepares every look and carries the imagery flag up', () => {
    const view = toRecommendationView(weddingWithinBudgetFixture, formatInr)
    expect(view.looks).toHaveLength(3)
    expect(view.hasDemoImagery).toBe(false)
    expect(view.budgetInr).toBe(25000)
  })

  it('raises the demo imagery flag as soon as one look is illustrative', () => {
    // A single demo item in a set of three is enough to require the label: the
    // shopper is looking at a partly illustrative grid and should know it.
    const view = toRecommendationView(vacationPartialFixture, formatInr)
    expect(view.hasDemoImagery).toBe(true)
  })
})

describe('LookVisual contract', () => {
  it('passes each backend visual kind through untouched', () => {
    expect(toLookView(styledLookFixture, 8000, formatInr).visualKind).toBe('complete_look')
    expect(toLookView(lookOneFixture, 8000, formatInr).visualKind).toBe('composite')
    expect(toLookView(gridLookFixture, 8000, formatInr).visualKind).toBe('grid')
  })
})
