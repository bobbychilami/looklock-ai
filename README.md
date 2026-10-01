# LOOKLOCK AI

An AI personal style and shopping assistant, built for the YouCam API Skin AI & eCommerce VTO Hackathon 2026.

The product loop: pick an occasion, pick a style preference, set a budget, upload a photo, get three personalised looks, try one on virtually, understand why it was chosen, and shop the pieces.

> **Status: the full loop works end to end.** AI Clothes Virtual Try-On V4.0 runs for real, and the product around it is built: a 28-item catalogue, a deterministic ranking engine, three ranked looks with a score breakdown, product try-on, and a shop-this-look price breakdown. The catalogue is fictional demo data and the app says so. See [`docs/LOOKLOCK_MVP.md`](docs/LOOKLOCK_MVP.md).

The exact vendor contract this is built against is written up in
[`docs/YOUTCAM_VTO_PROOF.md`](docs/YOUTCAM_VTO_PROOF.md), including the places
where the vendor's own documentation contradicts itself.

## Repository layout

```
.
├─ .env.example              # root template for backend secrets + frontend config
├─ .gitignore
├─ docs/
│  ├─ LOOKLOCK_MVP.md        # the product loop, ranking engine, privacy, limits
│  └─ YOUTCAM_VTO_PROOF.md   # transcribed AI Clothes V4.0 + File API contract
├─ frontend/                 # React + TypeScript + Vite + Tailwind CSS
│  ├─ src/
│  │  ├─ api/                # typed client for the LOOKLOCK backend
│  │  ├─ components/
│  │  │  ├─ layout/          # app shell
│  │  │  ├─ product/         # garment + look cards
│  │  │  └─ ui/              # design-system primitives
│  │  ├─ config/             # public runtime config (VITE_* only)
│  │  ├─ lib/                # display formatting (prices, slots, scores)
│  │  ├─ state/              # session context + reducer
│  │  └─ pages/
│  │     ├─ Home.tsx         # landing page
│  │     ├─ onboarding/      # occasion / style / budget / photo wizard
│  │     ├─ looks/           # the three ranked looks
│  │     ├─ look/            # one look, with its score breakdown
│  │     ├─ tryon/           # try-on progress
│  │     ├─ result/          # the generated image
│  │     ├─ shop/            # shop-this-look price breakdown
│  │     └─ dev/             # Status.tsx, VtoPoc.tsx
│  └─ vite.config.ts         # React + Tailwind plugins, /api dev proxy
└─ backend/                  # Python FastAPI
   ├─ app/
   │  ├─ api/
   │  │  ├─ deps.py          # FastAPI dependencies
   │  │  ├─ errors.py        # YouCam exceptions -> HTTP responses
   │  │  └─ routes/          # health, integration, tryon PoC, catalog, look_tryon
   │  ├─ catalog/            # product model, seed data, static source, generated assets
   │  ├─ core/
   │  │  ├─ config.py        # pydantic-settings configuration
   │  │  └─ image_validation.py
   │  ├─ recommendations/    # request/response schemas + deterministic ranking engine
   │  ├─ services/
   │  │  ├─ tryon.py         # job orchestration + phase progress
   │  │  └─ youcam/          # client / service / schemas / errors
   │  └─ main.py             # app factory, CORS, lifespan
   ├─ tools/
   │  └─ generate_catalog_assets.py   # pure-stdlib PNG artwork generator
   └─ tests/                 # pytest suite, all offline
```

## Architecture

```
browser (React)
   │  HTTP, JSON only
   │  GET /api/v1/...
   ▼
FastAPI backend
   │  Authorization: Bearer <YOUCAM_API_KEY>   ← key lives only here
   ▼
YouCam API  https://yce-api-01.makeupar.com
```

Two rules shape the layout:

**The YouCam API key never reaches the browser.** The frontend only ever talks to our own backend. `VITE_*` variables are public by definition, so no credential is read in `src/config/env.ts`. Every YouCam call is initiated from `backend/app/services/youcam/`.

**The vendor is isolated behind a service layer.** `YouCamClient` owns HTTP, auth, retries and polling. `YouCamService` owns feature-level operations and returns domain types (`SkinProfile`, `ColorTones`, `TryOnResult`) rather than raw vendor payloads. Routes depend on the service, never on `httpx`. A future API version change stays inside one directory.

Backend layering, outside-in:

```
routes/  →  services/youcam/service.py  →  services/youcam/client.py  →  httpx
             (domain types)                 (auth, retry, polling)      (transport)
```

## Prerequisites

- Node.js 20+ (developed on 24.x)
- Python 3.10+
- A YouCam API key from the [API console](https://yce.makeupar.com/api-console/en/api-keys/)

## Setup

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:

```
YOUCAM_API_KEY=<your key>
```

`YOUTCAM_API_KEY` is accepted as an alias, since that is the spelling used in the
hackathon brief. Set exactly one of them.

Without it the backend still starts and `/api/v1/health` works; YouCam-backed features report themselves as unconfigured instead of failing at runtime.

### 2. Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # Windows
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

On macOS/Linux use `source .venv/bin/activate` and `python -m ...` instead.

Verify: <http://localhost:8000/api/v1/health> and OpenAPI docs at <http://localhost:8000/docs>.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Verify: <http://localhost:5173>.

In development Vite proxies `/api` to the backend (see `frontend/vite.config.ts`), so the browser stays on one origin and CORS never enters the picture. In production, point a reverse proxy at both, or set `VITE_API_BASE_URL` to the deployed backend origin.

## Commands

| Where | Command | Purpose |
| --- | --- | --- |
| `backend` | `python -m pytest` | Test suite (offline, no API key) |
| `backend` | `python -m ruff check .` | Lint |
| `backend` | `python -m uvicorn app.main:app --reload` | Dev server |
| `frontend` | `npm run dev` | Dev server with HMR |
| `frontend` | `npm run build` | Typecheck (`tsc -b`) then production build |
| `frontend` | `npm run lint` | Lint (oxlint) |
| `frontend` | `npm run preview` | Serve the production build |

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness. Never calls YouCam, so a probe cannot burn units. |
| `GET` | `/api/v1/ready` | Reports whether an API key is present. No outbound call. |
| `GET` | `/api/v1/integration/ycam/status` | Which YouCam features are wired, and the known gaps. |
| `GET` | `/api/v1/catalog/looks` | Catalogue shape plus the occasion/style/budget vocabulary the wizard renders. |
| `GET` | `/api/v1/catalog/items` | The catalogue, with optional `slot`, `occasion`, `style`, `max_price_inr` filters. |
| `GET` | `/api/v1/catalog/items/{product_id}` | One product. |
| `GET` | `/api/v1/catalog/items/{product_id}/image` | Its generated artwork (`image/png`). |
| `POST` | `/api/v1/recommendations` | `{occasion, style, budget_inr}` → exactly three ranked looks, with reasons, a score breakdown, and a `notice` when constraints had to be relaxed. |
| `POST` | `/api/v1/tryon` | Try one catalogue garment on the shopper's photo. Multipart: `source_image`, `product_id`, optional `filter_multi_person`. Returns `202` with a `job_id`. |
| `GET` | `/api/v1/tryon/{job_id}` | Job phase, and the result URL once YouCam reports success. |
| `GET` | `/api/v1/integration/ycam/vto/options` | The documented `garment_category` and `filter_multi_person` enums. |
| `POST` | `/api/v1/integration/ycam/vto/test` | Start one try-on from two raw uploads. Returns `202` with a `job_id`. |
| `GET` | `/api/v1/integration/ycam/vto/test/{job_id}` | Job phase, and the result URL once YouCam reports success. |

`/api/v1/tryon` is the product route and reuses the PoC's job store, phase machine and
runner. The only difference is the reference: instead of the browser uploading a garment,
the backend resolves a `product_id` to a bundled asset and pushes it through the vendor's
own File API to get a `file_id`, because YouCam cannot fetch a local path.

### Why the try-on is two calls

YouCam's try-on is asynchronous and can take tens of seconds. Holding one HTTP
request open for that would time out any proxy in front of the backend and would
leave the browser with nothing to show. So `POST .../vto/test` validates both
images, queues the work and returns `202` plus a `job_id`; the browser then polls
`GET .../vto/test/{job_id}` and gets the real phase each time:

`queued` → `uploading_source_image` → `uploading_reference_image` →
`submitting_task` → `polling_task` → `completed` | `failed`

The demo page at <http://localhost:5173/dev/vto> renders that as a step list, and
shows the vendor's own `task_status` while polling.

Jobs live in a bounded, TTL-scoped dict inside the backend process. **Nothing is
persisted** — see [Known gaps](#known-gaps).

## YouCam integration notes

Everything below is transcribed from the official documentation at <https://docs.makeupar.com>. No endpoint, field name or enum was guessed. The full write-up, including the undocumented bits and the documentation's own internal contradictions, is in [`docs/YOUTCAM_VTO_PROOF.md`](docs/YOUTCAM_VTO_PROOF.md).

**Host and auth**

- API server: `https://yce-api-01.makeupar.com`
- Auth on all v2 endpoints: `Authorization: Bearer <API_KEY>`
- Keys: <https://yce.makeupar.com/api-console/en/api-keys/>

**Endpoints wired up** (`backend/app/services/youcam/service.py`)

| Purpose | Method + path |
| --- | --- |
| File upload | `POST /s2s/v2.0/file` |
| AI Skin Analysis v2.0 | `POST /s2s/v2.0/task/skin-analysis` |
| AI Skin Analysis status | `GET /s2s/v2.0/task/skin-analysis/{task_id}` |
| AI Facial Color Tones Analyzer | `POST /s2s/v2.0/task/skin-tone-analysis` |
| Color tone status | `GET /s2s/v2.0/task/skin-tone-analysis/{task_id}` |
| AI Clothes Virtual Try-On v4.0 | `POST /s2s/v2.0/task/cloth-v4` |
| Try-on status | `GET /s2s/v2.0/task/cloth-v4/{task_id}` |
| Feature unit costs | `GET /s2s/v2.0/credit/feature-cost` |

**Workflow constraints that shaped the client**

- *Uploading is two steps.* `POST /s2s/v2.0/file` only reserves a slot and returns a presigned URL. The bytes must then be PUT to that URL before the resulting `file_id` is usable. `YouCamService.upload_image` performs both steps in order, and the docs are explicit that skipping step 2 produces a 404/500 while units are still charged.
- *V4.0 always needs a reference garment.* Every request variant of `RunClothV4Task` requires either `ref_file_id` or `ref_file_url`. Unlike V2.0 there is no `template_id` variant, so "try on a template" is not available on V4.0 at all.
- *AI tasks are asynchronous.* Submit returns a `task_id`, then the status endpoint is polled until `task_status` is `success` or `error`. `YouCamClient.await_task` handles this with a bounded budget and reports each observed status to its caller.
- *Polling is mandatory.* A task that is not polled within the retention window can expire as `InvalidTaskId` even though it processed successfully and units were deducted.
- *Retention.* Uploaded files and `file_id` live 30 days; `task_id` lives 30 days; result download URLs expire after 2 hours.
- *Rate limit.* 250 requests per 300 seconds, enforced per IP **and** per token. Both must be satisfied. The client retries on 429 and 5xx with exponential backoff plus jitter, honouring `Retry-After` when present.
- *Error taxonomy.* Engine-level failures (`error_pose`, `error_invalid_ref`, `error_nsfw_content_detected`, …) surface on a task with `task_status: "error"`, in `data.error` as an `EngineErrorCode`. They are mapped to actionable messages in `client.py` and converted to HTTP responses in `api/errors.py`. When the vendor omits `error_message`, our mapping for the code is used instead.
- *Image size and format.* Documented limits are 10 MB and jpg/png. `core/image_validation.py` enforces both **before** any vendor call, by sniffing the leading bytes rather than trusting the multipart `Content-Type`.

**Choices made where the API offers options**

| Decision | Value | Why |
| --- | --- | --- |
| Skin analysis actions | `hd_skin_type`, `hd_texture`, `hd_oiliness`, `hd_moisture`, `hd_radiance`, `hd_redness` | HD and SD actions cannot be mixed in one request. These six feed the "why this look" narrative. |
| Skin analysis `format` | `json` | Returns scores inline; `zip` would require server-side unpacking. |
| `face_angle_strictness_level` | `medium` | Docs default to `high`, which assumes controlled capture. User uploads are less reliable. |
| `garment_category` | caller-supplied, default `auto` | `auto` lets the engine classify the reference garment. |
| `filter_multi_person` | `off` | Rejecting photos taken with friends would be a bad first-run experience. |
| Source and reference as URLs | file ids instead | `src_file_url` / `ref_file_url` must be publicly reachable, which the demo cannot offer. Both images are uploaded instead. |
| Client-side min image size | not enforced | The docs say 128 px in one place and 320 px in another. Rather than pick one, we let the engine answer. |
| Completion handling | polling | Webhooks are documented as preferred but need a public endpoint and signature verification; polling ships first. |

### Deliberately not wired

- `GET /s2s/v1.0/client/credit` uses the legacy v1 access-token flow, which requires a separate authentication call. Not implemented; use `/s2s/v2.0/credit/feature-cost` for pricing.
- Webhook-based task completion.
- `POST /s2s/v2.0/task/delete` for explicit cleanup.

## What exists today

Working and verified:

- Monorepo skeleton, gitignore, environment templates, this README.
- FastAPI app with CORS, lifespan-managed HTTP client, and OpenAPI docs.
- `GET /api/v1/health`, `/ready`, `/integration/ycam/status`.
- YouCam client with bearer auth, retry/backoff, task polling, and full error mapping.
- YouCam service covering file upload, skin analysis, colour-tone analysis, and apparel virtual try-on.
- `ClothV4TaskRequest`, a Pydantic model transcribed from `RunClothV4Task`, which enforces the documented "exactly one of `*_file_id` / `*_file_url`" rule locally and rejects undocumented fields instead of forwarding them.
- Pre-flight image validation (size + magic-byte format) so a bad file never reaches the vendor.
- The full try-on flow behind `POST`/`GET /api/v1/integration/ycam/vto/test`, with real per-phase progress.
- **Product catalogue**: `Product`/`ProductImage` domain model, a 28-item fictional seed, a `ProductSource` implementation, and 28 original 1000×1250 PNGs generated by a pure-stdlib script (no Pillow, no scraped imagery). Accessories are display-only and are rejected as try-on references.
- **Recommendation engine**: deterministic, pure, with occasion/style/budget/completeness scoring, a diversity constraint on selection, monotonic over-budget scoring, and a stated relaxation order when the catalogue cannot fill three looks.
- **Product try-on**: `POST`/`GET /api/v1/tryon` reusing the PoC runner while resolving the reference garment from the catalogue.
- The full React product loop: landing, four-step wizard, three looks, look detail with score breakdown, try-on progress, result, and the shop-this-look price breakdown.
- 87 backend tests, all offline. Response fixtures are transcribed from the vendor's published examples, so a payload change surfaces as a failure.
- Frontend build (`tsc -b` + Vite) and lint (oxlint) pass with no warnings.
- The product try-on was confirmed working against the live YouCam API: photo upload, bundled-garment upload via the File API, task submission, polling to `success`, and a presigned result URL.

## Known gaps

These are the honest limits of this phase, not oversights.

- **The catalogue is fictional.** 28 invented products with illustrative prices and no retailer behind them, so `purchase_url` is `None` everywhere and the shop page shows "Demo" rather than a buy button. Nothing can be purchased, and a real PIM or retailer feed is the obvious next step.
- **Result URLs expire after 2 hours and cannot be refreshed.** We display the presigned link and nothing else. No result image is downloaded, cached or stored, and the `task_id` is discarded when the response is sent. Reload the page after two hours and the image is gone. Fixing this needs either our own object storage or a retained `task_id` to re-poll.
- **Jobs are in process memory only.** A backend restart loses every in-flight job, and there is no queue, no retry and no idempotency.
- **Session state is in the browser tab only.** The wizard's answers and the photo live in a React context; a refresh loses them. This is intentional for privacy, but it does mean there is no back button that survives a reload.
- **Look ids are per-response labels, not persistent identifiers.** `look-1` means "the first look in the response currently in memory".
- **The unit cost of V4.0 is not published.** The docs price V2.0 and V3.0 at 2 units each and omit V4.0. `GET /s2s/v2.0/credit/feature-cost` is wired but never surfaced, and unit accounting is not shown anywhere in the UI.
- **Generative try-on approximates fit and drape.** It is a strong hint, not a fitting-room photograph; faces, hands and unusual poses are the usual failure points.
- **The vendor's documentation is internally inconsistent** in four places (malformed `FileResponseV2` schema, contradictory minimum image size, contradictory target-image framing, mixed header types). Each is documented rather than papered over; see `docs/YOUTCAM_VTO_PROOF.md` §10.
- **No accounts, no persistence, no webhook completion.**

## Security

- `.env` is git-ignored; `.env.example` carries no real values.
- The YouCam API key is read only by `backend/app/core/config.py` and never returned by any route. Tests assert that no endpoint's payload contains the key or the variable name.
- Only the base URL is exposed, which is public documentation.
- Presigned upload URLs point at third-party storage, not at YouCam. `upload_file_bytes` therefore uses a **separate `httpx` client with no default headers**, so the API key cannot leak to that host and no extra header can invalidate the URL signature.
- User-supplied file names are never forwarded to the vendor; we send a name we chose (`looklock-source.jpg` / `looklock-reference.png`).
- Upload bodies are read with a hard 10 MB + 1 byte ceiling, and the declared content type must agree with the sniffed bytes.

## License

Unlicensed prototype built for the hackathon.
