/**
 * The recommendation engine's own account of how it reached these looks.
 *
 * The backend distinguishes four situations and each one needs different words:
 *
 * 1. every look fits the budget;
 * 2. some looks fit and some do not - the affordable ones are listed first;
 * 3. nothing affordable is appropriate for the occasion asked for;
 * 4. the catalogue is too small to produce three looks at all.
 *
 * Collapsing these into a generic "we adjusted your results" would be the easiest
 * thing to write and the wrong one: in case 3 the shopper's budget was not the
 * problem, and saying so is the difference between an honest limit and looking
 * broken. The backend writes that explanation itself, in shopper-facing language,
 * so `notice` is rendered verbatim and the surrounding UI only frames it.
 */

import type { BudgetView } from '@/api/normalize'
import { formatInr } from '@/lib/format'

export function BudgetNotice({
  budget,
  className = '',
}: {
  budget: BudgetView
  className?: string
}) {
  if (budget.status === 'met') return null

  const headline = headlineFor(budget)

  return (
    <div
      role="status"
      data-budget-status={budget.status}
      className={`border-l-2 border-accent-600 bg-accent-100/40 px-5 py-4 ${className}`}
    >
      <p className="text-sm font-medium text-accent-700">{headline}</p>
      {/* The engine's own words, unmodified. It names the real price of being
          correctly dressed, which is more useful than anything this component
          could paraphrase it as. */}
      {budget.hasNotice && budget.notice && (
        <p className="mt-1.5 text-sm text-accent-700">{budget.notice}</p>
      )}
    </div>
  )
}

/**
 * One line of framing per budget state. The switch is total over `BudgetStatus`
 * so a fourth variant cannot be added without this function being revisited.
 */
function headlineFor(budget: BudgetView): string {
  switch (budget.status) {
    case 'none_affordable':
      return `Nothing appropriate here fits ${formatInr(budget.budgetInr)}.`
    case 'partial':
      return `${budget.inBudgetCount} of ${budget.inBudgetCount + budget.overBudgetCount} looks fit your ${formatInr(budget.budgetInr)} budget.`
    case 'thin_catalogue':
      return 'This catalogue could not fill three looks for these answers.'
    // Unreachable: `met` returns null above. Listed so the switch stays total.
    case 'met':
      return ''
  }
}
