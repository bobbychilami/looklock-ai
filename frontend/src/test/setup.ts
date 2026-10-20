/**
 * Vitest setup.
 *
 * Only two things are needed. `@testing-library/jest-dom` adds matchers such as
 * `toBeInTheDocument` and `toHaveAttribute`, which read far better than raw
 * `expect(node).not.toBeNull()` in assertions about links and their safety
 * attributes. The `afterEach` cleanup is automatic in modern React Testing
 * Library, but doing it explicitly keeps the intent obvious and makes the file
 * safe if that default ever changes.
 */

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
