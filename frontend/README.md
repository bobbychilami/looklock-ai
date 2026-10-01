# frontend

React + TypeScript + Vite + Tailwind CSS. Part of [LOOKLOCK AI](../README.md).

## Commands

```bash
npm install
npm run dev        # dev server with HMR at http://localhost:5173
npm run build      # typecheck (tsc -b) then production build to dist/
npm run preview    # serve the production build
npm run lint       # oxlint
```

## Configuration

```bash
cp .env.example .env.local
```

`VITE_API_BASE_URL` points at the backend. It is optional in development: `vite.config.ts` proxies `/api` to `http://localhost:8000`, so requests work on a single origin with no CORS involved.

Anything prefixed `VITE_` is inlined into the client bundle and is public. No credential is ever read from a `VITE_*` variable. The browser calls only our backend, which holds the YouCam API key.

## Structure

```
src/
├─ api/
│  ├─ client.ts      fetch wrapper; turns failures into ApiRequestError
│  ├─ looklock.ts    endpoint functions
│  └─ types.ts       types mirroring the backend response models
├─ components/
│  ├─ layout/        AppShell
│  └─ ui/            Card, Badge, Button
├─ config/env.ts     public runtime config
└─ pages/            route components
```

`@/` is aliased to `src/`.

## Conventions

- Tailwind v4 via `@tailwindcss/vite`; brand tokens are CSS custom properties in `src/index.css`.
- Design-system primitives take a `variant` prop mapped to a class lookup, not raw class strings from call sites.
- Types for backend payloads are declared once in `src/api/types.ts`; keep them in sync with the FastAPI response models.
- No state management library yet. Add one only when the product loop's state actually needs it.
