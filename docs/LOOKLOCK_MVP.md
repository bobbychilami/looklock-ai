# LOOKLOCK MVP

A demo of the product loop: answer four questions, get three ranked outfits, try the
top on your own photo, then take the price breakdown with you.

The styling, ranking and shopping decision are LOOKLOCK's. The generated try-on image
is YouCam's. The split matters, so it is worth stating plainly before anything else.

## The loop

```
Landing  ->  Onboarding (occasion, style, budget, photo)  ->  Your Looks (3)
       ->  Look detail  ->  Try-on progress  ->  Result  ->  Shop this look
```

- `/` landing page
- `/create` the four-step wizard
- `/looks` the three ranked outfits
- `/look/:lookId` one outfit in full, with its score breakdown
- `/tryon/:productId` virtual try-on progress
- `/result/:jobId` the generated image
- `/shop` full price breakdown
- `/dev/status` backend and YouCam diagnostics
- `/dev/vto` the raw integration harness

## Division of responsibility

| Concern | Owner |
| --- | --- |
| Occasion/style/budget intake | LOOKLOCK |
| Outfit assembly and ranking | LOOKLOCK (`app/recommendations/`) |
| Explaining a rank | LOOKLOCK (score breakdown + reasons) |
| Garment catalogue | LOOKLOCK (`app/catalog/`, bundled demo data) |
| Price breakdown | LOOKLOCK |
| Generated worn image | YouCam AI Clothes Virtual Try-On V4.0 |
| Photo upload, task submit, polling | LOOKLOCK backend, calling YouCam |

LOOKLOCK never calls YouCam from the browser. The API key stays in the backend
environment; `frontend/src/config/env.ts` reads only `VITE_*` values, which are public
by definition.

## The recommendation engine

`POST /api/v1/recommendations` takes `{occasion, style, budget_inr}` and returns exactly
three looks, ranked. It is pure and deterministic: the same catalogue and the same
answers always produce the same three looks in the same order, so there is no
client-side shuffling and no way to blame randomness for a result.

### How a look is scored

Every outfit is a top + bottom, optionally plus footwear and an accessory. Each candidate
is scored on four axes and the components are shown in the UI, because a rank the shopper
cannot interrogate is a rank they have to take on faith.

| Component | Weight | What it measures |
| --- | --- | --- |
| `occasion` | 0.35 | Share of the outfit's items that fit the occasion |
| `style` | 0.25 | Share of items that match the style |
| `budget` | 0.25 | How well the total uses the stated budget |
| `completeness` | 0.15 | Optional slots filled (footwear 2, accessory 1) |

Budget handling is worth calling out, because the obvious implementation is wrong.
Scoring an over-budget outfit as `0` makes every over-budget look tie at zero, so the
tie-break would then pick an arbitrary expensive outfit rather than the least-bad one.
Instead the budget score decays monotonically with the overshoot and is floored at
`OVER_BUDGET_FLOOR = 0.45`, so among otherwise equal over-budget looks the one closest to
the budget wins.

### How three looks get chosen

1. Build every combination of top x bottom x (footwear or none) x (accessory or none),
   with accessories filtered to the requested occasion.
2. Score them, then sort by total with a stable tie-break on product ids.
3. Greedily pick 3 with a diversity constraint: no more than 1 shared product between
   looks at first (`IDEAL_MAX_SHARED`), relaxing to 2, then to unconstrained only if the
   catalogue cannot fill three.
4. If the catalogue cannot produce three looks within budget, relax in a stated order and
   report it via `notice` and `relaxed_constraints` rather than silently returning fewer
   or over-budget results.

The returned `look_id`s (`look-1`, `look-2`, `look-3`) are per-response labels, not
persisted identifiers. A look is only addressable while the response that carried it is in
the browser.

## The catalogue

28 original products, all fictional: 10 tops, 8 bottoms, 5 footwear, 5 accessories.

They are demo data, and the app says so wherever they appear. Every product has
`purchase_url = None` and `is_demo = true`, and the shop page shows "Demo" rather than a
buy button. Inventing retailer links for products that do not exist would misrepresent
them; there is nothing to link to.

Artwork is generated, not sourced. `backend/tools/generate_catalog_assets.py` is a
pure-stdlib PNG writer - no Pillow, no numpy, no scraped photography - producing 1000x1250
illustrations. Regenerate with:

```bash
cd backend
python tools/generate_catalog_assets.py
```

Accessories are display-only. They contribute to a look's completeness score and appear in
the breakdown, but they are rejected by `require_reference()` and can never become a
try-on reference, because there is no meaningful way to "put on" a pocket square.

## Try-on: the one genuinely new piece

`POST /api/v1/tryon` reuses the Phase 2 VTO machinery rather than reimplementing it - same
job store, same phase machine, same runner, same vendor client. A second copy of that
orchestration would just be a second thing to keep in step with the vendor.

What is new is resolving the reference garment. The catalogue product is a file inside the
Python package, and YouCam cannot fetch a local path, so the asset is read from disk,
validated like any upload, and pushed through the vendor's own File API to obtain a
`file_id`. That deliberately reuses the documented upload path rather than inventing a
URL-reachability trick that would only work on a developer's laptop.

The browser sends only the photo and a `product_id`. Validation order is deliberate: the
API key is checked first (nothing can succeed without it), the photo second (a bad upload
should cost no vendor request), and the catalogue last (a typo should not make the shopper
wait on an upload).

### Phases

`queued` -> `uploading_source_image` -> `uploading_reference_image` -> `submitting_task`
-> `polling_task` -> `completed` | `failed`

These are internal pipeline names. The UI maps them to shopper-facing copy
(`Sending your photo`, `Building your look`, ...) in
`frontend/src/pages/tryon/TryOn.tsx`, and also mirrors the raw phase onto a `data-phase`
attribute, because the first question when a run fails is which step broke.

## Privacy and retention

Stated the way the vendor actually behaves, not optimistically:

- The photo is sent to YouCam to generate the try-on image. That is a third-party
  processor, and the consent checkbox in the wizard says so before anything is uploaded.
- LOOKLOCK stores nothing. Session state is a React context, held in memory; the answers
  and the photo are lost on refresh. Nothing goes to `localStorage`.
- The result is a presigned YouCam URL on `yce-us.s3-accelerate.amazonaws.com` with a
  roughly two-hour expiry. We do not copy or cache the image, so a dead link really is
  dead.
- Try-on jobs live in an in-memory store with a TTL and vanish on restart. An unknown job
  id returns 404 with that stated plainly.
- No analytics, no auth, no database, no third-party scripts.

The app does not claim photos stay on-device, are never stored, or are 100% private.
They are not: they are transmitted to a vendor to do the thing the user asked for.

## Limitations

- The catalogue is 28 fictional items. It cannot represent real inventory or real prices.
- Generative try-on approximates fit and drape. It is a strong hint, not a fitting-room
  photograph. Faces, hands and unusual poses are the usual failure points.
- Ranking is a weighted heuristic, not a model. It is explainable, deterministic and
  inspectable, which is why it is here instead of an opaque model.
- Low budgets can force relaxation, because the catalogue has no items below ~₹900.
- Not responsive-tuned past a usable desktop and phone layout; not localised.
- Single-user, no persistence, no accounts.

## Running it

Backend:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env      # add YOUCAM_API_KEY
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to the backend, so the app needs no configuration in
the default setup. Set `VITE_API_BASE_URL` only when the API is on a different origin;
`assetUrl()` in `src/config/env.ts` re-bases the catalogue's root-relative image URLs,
which otherwise stop resolving off the same origin.

Without `YOUCAM_API_KEY` the app still works for styling, ranking and the price
breakdown. Only the try-on returns 503.

## Verification

```bash
cd backend  && ruff check app tests tools && pytest -q     # 87 passed
cd frontend && npm run lint && npm run build               # 0 warnings, builds
```

The backend suite covers the engine (determinism, ranking, diversity, budget relaxation,
thin inventory), the catalogue (asset resolution, filters, validation) and the product
try-on (every documented phase, vendor failure, secret hygiene). The YouCam transport is
mocked; the real vendor chain is verified by running it, and was confirmed working
end to end - photo upload, bundled-garment upload through the File API, task submission,
polling, and a presigned result URL.

See `YOUTCAM_VTO_PROOF.md` for the vendor contract itself.
