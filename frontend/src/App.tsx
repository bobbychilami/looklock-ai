import { RouterProvider, createBrowserRouter } from 'react-router-dom'

import Home from '@/pages/Home'
import LookDetail from '@/pages/look/LookDetail'
import Looks from '@/pages/looks/Looks'
import Onboarding from '@/pages/onboarding/Onboarding'
import Result from '@/pages/result/Result'
import Shop from '@/pages/shop/Shop'
import TryOn from '@/pages/tryon/TryOn'
import Status from '@/pages/dev/Status'
import VtoPoc from '@/pages/dev/VtoPoc'
import { LookSessionProvider } from '@/state/LookSessionProvider'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Home />,
  },
  {
    path: '/create',
    element: <Onboarding />,
  },
  {
    path: '/looks',
    element: <Looks />,
  },
  {
    path: '/look/:lookId',
    element: <LookDetail />,
  },
  {
    path: '/tryon/:productId',
    element: <TryOn />,
  },
  {
    path: '/result/:jobId',
    element: <Result />,
  },
  {
    path: '/shop',
    element: <Shop />,
  },
  {
    // Developer tools. Deliberately outside the shopper journey: the status page
    // reports the integration surface, and the proof of concept is the raw
    // vendor harness rather than the product's own try-on route.
    path: '/dev/status',
    element: <Status />,
  },
  {
    path: '/dev/vto',
    element: <VtoPoc />,
  },
])

export default function App() {
  // One provider above the whole router: the wizard, the looks, the detail page and
  // the result all read the same session, so a full page load inside the flow is
  // the only thing that loses it - and that is the intended, privacy-preserving
  // behaviour.
  return (
    <LookSessionProvider>
      <RouterProvider router={router} />
    </LookSessionProvider>
  )
}
