# YouCam VTO Proof of Concept — documented API reference

Everything below is transcribed from the official YouCam API documentation.
**No endpoint, field, enum or auth mechanism in this document was guessed.**

| Source | URL |
| --- | --- |
| AI Clothes Virtual Try-On overview + integration guide | <https://docs.makeupar.com/reference/ai_clothes/section/overview> |
| AI Clothes V4.0 OpenAPI description | `https://docs.makeupar.com/_bundle/reference/ai_clothes.json` |
| AI Clothes V4.0 endpoints | <https://docs.makeupar.com/reference/ai_clothes/v4.0> |
| File Management OpenAPI description | `https://docs.makeupar.com/_bundle/reference/file.json` |
| Quick Start Guide | <https://docs.makeupar.com/develop/quick_start_guide> |
| API Server | <https://docs.makeupar.com/develop/api_server> |
| Rate Limit | <https://docs.makeupar.com/develop/rate_limit> |
| File Retention Period | <https://docs.makeupar.com/develop/file_retention_period> |
| Error Codes | <https://docs.makeupar.com/develop/error_codes> |
| Unit System | `https://docs.makeupar.com/_bundle/reference/unit_system.json` |

Retrieved for this phase. Docs version observed: `v1.16` (developer guide
header) / `AI Clothes Virtual Try-On` OpenAPI.

---

## 1. Selected feature

**Name:** AI Clothes Virtual Try-On
**Engine version:** V4.0 (latest of V2.0 / V3.0 / V4.0)
**OpenAPI `x-display-name`:** `AI Clothes Virtual Try-On`
**OpenAPI `x-engine-version`:** `V4.0`

Rationale: it is the smallest documented operation that exercises the complete
LOOKLOCK image flow (upload a user image, upload a reference garment, submit an
async task, poll, receive a result image URL) and it is the feature the
hackathon brief names. V4.0 was chosen over V2.0 because it adds the `outer`
garment category and `filter_multi_person`, both relevant to outfit swaps.

---

## 2. Endpoints

| Step | Method | Path |
| --- | --- | --- |
| 1. Reserve upload slot | `POST` | `/s2s/v2.0/file` |
| 2. Upload image bytes | `PUT` | *(presigned URL from step 1 — not the YouCam host)* |
| 3. Submit try-on task | `POST` | `/s2s/v2.0/task/cloth-v4` |
| 4. Poll task status | `GET` | `/s2s/v2.0/task/cloth-v4/{task_id}` |

**Host:** `https://yce-api-01.makeupar.com` (the single server declared in the
OpenAPI `servers` array).

---

## 3. Authentication

Security scheme name: `BearerAuthenticationV2`, type `http`, scheme `bearer`.

```
Authorization: Bearer YOUR_API_KEY
```

The scheme description states verbatim:

> Use the standard 'Bearer authentication'. Put your 'API Key' in header:
> `Authorization:Bearer YOUR_API_KEY`. Notice that there is ' ' a space between
> 'Bearer' and the 'YOUR_API_KEY'.

Applied to all four steps. The presigned storage URL in step 2 is **not** on the
YouCam host and carries its own signature; the vendor's own `curl` sample sends
only `Content-Type` and `Content-Length` there.

The integration guide documents this invalid-key response:

```json
{
  "status": 401,
  "error": "Unauthorized",
  "error_code": "InvalidAccessToken"
}
```

---

## 4. Step 1 — File Management

### Request

`POST /s2s/v2.0/file`, `Content-Type: application/json`.

Schema `FileV1.1`, `files` is **required**, each entry requires all three fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `content_type` | string | yes | Documented limits: 10 MB image, 100 MB video |
| `file_name` | string | yes | |
| `file_size` | integer | yes | bytes |

Vendor example:

```bash
curl --request POST \
  --url https://yce-api-01.makeupar.com/s2s/v2.0/file \
  --header 'Authorization: Bearer YOUR_API_KEY' \
  --header 'content-type: application/json' \
  --data '{
  "files": [
 {
  "content_type": "image/jpg",
  "file_name": "full_body_photo_01_3dbd1b6683.jpg",
  "file_size": 547541
 }
    ]
  }'
```

### Response

```json
{
  "status": 200,
  "data": {
    "files": [
      {
        "content_type": "image/jpg",
        "file_name": "full_body_photo_01_3dbd1b6683.jpg",
        "file_id": "SaGaqpDgKwFrVBgMpQMA3HY0LeqdT9/13W5TOD8/u/FfjK3xgCQ+hRt9MJXBFaud",
        "requests": [
          {
            "method": "PUT",
            "url": "https://yce-us.s3-accelerate.amazonaws.com/demo/ttl30/...signature...",
            "headers": {
              "Content-Length": "547541",
              "Content-Type": "image/jpg"
            }
          }
        ]
      }
    ]
  }
}
```

`BasicFileResponse` documents `file_id`, `requests[].url`, `requests[].method`,
`requests[].headers`, `content_type` and `file_name`.

> Note: the published `FileResponseV2` schema declares `data: null` alongside a
> `$ref`, which is malformed. The `curl` sample and `BasicFileResponse` agree
> that the descriptors live under `data.files`. Our parser accepts `data.files`
> and also tolerates a top-level `files` array because of this schema defect.

### Critical behaviour

Calling `POST /s2s/v2.0/file` **does not upload anything.** It only reserves the
slot and returns a presigned URL. The bytes must then be uploaded separately:

> Simply calling the File API does not upload your file. You must **manually
> upload** the file to the **URL provided in the File API response**. … you will
> get a 500 Server Error / unknown_internal_error or 404 Not Found error when
> using AI APIs if you do not upload the file to the URL provided in the File API
> response.

---

## 5. Step 3 — Submit the try-on task

### Request

`POST /s2s/v2.0/task/cloth-v4`, `Content-Type: application/json`.

Schema `RunClothV4Task` is an `allOf` of an `anyOf` of four variants plus optional
properties.

**Source image — exactly one of (each variant requires the pair):**

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `src_file_id` | string | one of | From the File API |
| `src_file_url` | string | one of | Must be publicly accessible |

**Reference garment — exactly one of (each variant requires the pair):**

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_file_id` | string | one of | From the File API |
| `ref_file_url` | string | one of | Must be publicly accessible |

**Garment category — required in all four V4 variants:**

| Field | Type | Required | Enum |
| --- | --- | --- | --- |
| `garment_category` | string | yes | `full_body`, `lower_body`, `upper_body`, `shoes`, `auto`, `outer` |

Documented description: *"The category of garment of reference image. It's
required if reference image provided. Utilize the 'auto' parameter to allow the AI
engine to automatically identify and classify garment categories."*

**Optional:**

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `change_shoes` | boolean | `true` | Only has effect when `garment_category` is `full_body` or `lower_body` |
| `filter_multi_person` | string | `off` | Enum: `off`, `normal`, `strict` |

`filter_multi_person` semantics, verbatim:

- `off` — No filtering. The engine uses the largest person in the image.
- `normal` — Reject when another person is comparable in size to the main subject,
  or is clearly visible on the same plane… Typical group or two-person photos.
  Distant or blurry background people are ignored.
- `strict` — Reject when any additional person is visible, including small,
  distant, background, or blurry / out-of-focus people.

> **V4.0 has no template-based variant.** `template_id` exists only in the V2.0
> schema (`RunClothsTaskV2`), not in `RunClothV3Task` or `RunClothV4Task`. For
> V4.0 a reference garment image or a publicly reachable reference URL is
> **mandatory**.

### The smallest documented valid request

```bash
curl --request POST \
  --url https://yce-api-01.makeupar.com/s2s/v2.0/task/cloth-v4 \
  --header 'Authorization: Bearer YOUR_API_KEY' \
  --header 'content-type: application/json' \
  --data '{
    "src_file_url": "https://plugins-media.makeupar.com/strapi/assets/clothes_03_cccd5d4803.jpeg",
    "ref_file_url": "https://plugins-media.makeupar.com/strapi/assets/clothes_reference_full_body_01_5a000d999f.png",
    "garment_category": "full_body"
  }'
```

Our proof of concept uses the file-id variant, since we upload both images
ourselves and have no publicly reachable hosting:

```json
{
  "src_file_id": "<file_id from step 1>",
  "ref_file_id": "<file_id from step 1>",
  "garment_category": "auto",
  "filter_multi_person": "off"
}
```

### Response

Schema `BasicRunTaskResponseV2`:

```json
{
  "status": 200,
  "data": {
    "task_id": "SaGaqpDgKwFrVBgMpQMA3HY0LeqdT9_13W5TOD8_u_GPi6NqQ3dhlmN-6ntFwhzT"
  }
}
```

---

## 6. Step 4 — Poll task status

### Request

`GET /s2s/v2.0/task/cloth-v4/{task_id}`, `Authorization: Bearer YOUR_API_KEY`.

### Response

Schema `TaskStatusResponseV2`:

```json
{
  "status": 200,
  "data": {
    "task_status": "success",
    "error": null,
    "error_message": null,
    "results": {
      "url": "https://yce-us.s3-accelerate.amazonaws.com/demo/ttl30/...signature..."
    }
  }
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `data.task_status` | string | Enum: `running`, `success`, `error` |
| `data.error` | string / null | An `EngineErrorCode` (see §8) |
| `data.error_message` | string | Detailed description |
| `data.results.url` | string | *"URL to download this result. Valid for 2 hours"* |

The result image is a **single URL**; V4.0 returns one image, not an array.

Documented responses on this endpoint: `200`, `400` (invalid task ID), `401`,
`500` (task execution timeout).

Documented polling guidance: poll at regular intervals (e.g. every 10 seconds)
until `task_status` is `success` or `error`, and do not stop polling within the
retention window or the task may expire as `InvalidTaskId` while units are still
charged.

---

## 7. Documented operational limits

| Limit | Value | Source |
| --- | --- | --- |
| Rate limit | 250 requests / 300 s, per IP **and** per token | Rate Limit |
| Recommended pacing | ~5 requests per second | Rate Limit |
| File / `file_id` retention | 30 days | File Retention Period |
| `task_id` retention | 30 days | File Retention Period |
| Result download URL validity | 2 hours | File Retention Period |
| Image max file size | < 10 MB | File Specs & Errors |
| Image formats | jpg / png | File Specs & Errors |
| Image dimensions | 1024×768 recommended, 512×384 minimum, max side 4096 px | File Specs & Errors |
| Minimum dimension | long side ≥ 128 px (AI Clothes) | AI Clothes Error Codes |

### Target user image requirements (verbatim from File Specs)

> - Single person only.
> - The person should occupy at least 80% of the frame for optimal results.
> - Images should include the upper body only, from the chest upwards. There is
>   no need to show the abdomen, but the shoulders should be visible.
> - The face must be fully visible, with no obstructions.
> - The body must be facing forward in a standing position (no sitting or
>   crouching).

### Reference garment requirements (verbatim, abridged)

> - If Using a Real-Person Clothing Photo as Reference: must feature only one
>   person; the visible clothing area must fully cover the intended try-on area
>   (for full-body try-on a half-body clothing image is not acceptable); the
>   clothing must not be heavily obstructed; face fully visible; body facing
>   forward in a standing position.
> - If Using a Product Image as Reference: must be a front-facing product shot of
>   a single garment; do not use composite images (e.g. top and bottom in one
>   photo); **for the lower body, only actual worn outfits are supported, not
>   standalone product images.**

---

## 8. Error formats

### Run-task error (HTTP 400 on submit)

Schema `RunError`:

```json
{
  "status": 400,
  "error": "The operation could not be completed",
  "error_code": "InvalidParameters"
}
```

`error_code` enum: `InvalidParameters`, `CreditInsufficiency`,
`InvalidStyleGroup`, `InvalidStyle`, `BadRequest`.

### Auth error (HTTP 401)

```json
{ "status": 401, "error": "Invalid API key" }
```

The integration guide additionally shows
`{ "status": 401, "error": "Unauthorized", "error_code": "InvalidAccessToken" }`.
Both shapes are accepted.

### Rate limit (HTTP 429)

```json
{ "status": 429, "error": "Too many requests" }
```

### Task-level errors (HTTP 200, `task_status: "error"`)

**Preprocess:**

| Code | Description |
| --- | --- |
| `exceed_max_filesize` | SRC or REF image too large; long side must not exceed 4096 px |
| `error_below_min_image_size` | SRC or REF image too small; long side must be at least 128 px |
| `error_pose` | Pose could not be detected from the uploaded human SRC image |
| `error_invalid_ref` | REF image is invalid, e.g. empty or subject not fully visible |
| `error_apply_region_mismatch` | Apply region in SRC does not match REF |
| `error_invalid_src` | SRC shows only the lower body or only the feet |

**Engine:**

| Code | Description |
| --- | --- |
| `invalid_parameter` | Invalid garment category; invalid `src_keys`/`dst_keys`/`acts`; invalid `ref_keys` or `template_ref_image`; *exactly one of them must be provided* |
| `error_download_image` | SRC or REF image could not be downloaded |
| `exceed_max_filesize` | File size must not exceed 10 MB |
| `error_nsfw_content_detected` | NSFW content detected in the result image |
| `error_editing_failed` | Result image too similar to the source image |
| `unknown_internal_error` | Failed to load the model; invalid scheduler; no engine loaded; the file is not in the upload results |
| `error_multi_person` | Multiple individuals detected under `normal` or `strict` filter |

The `EngineErrorCode` enum in the OpenAPI also lists codes shared with other
features (`error_decode_image`, `error_no_face`, `error_face_parsing`,
`error_inference`, `error_upload`, `exceed_nsfw_retry_limits`,
`error_exceed_max_image_size`, `error_download_mask`, `error_decode_mask`).
We tolerate any of them.

### Poll-endpoint errors

| Status | Body | Meaning |
| --- | --- | --- |
| `400` | `{"status": 400, "error": "Invalid task ID"}` | Task expired or never existed |
| `401` | `{"status": 401, "error": "Invalid API key"}` | |
| `500` | `{"status": 500, "error": "Task execution timed out"}` | |

---

## 9. Unit cost

The AI Clothes Virtual Try-On page documents:

| AI Feature | Unit Consumed |
| --- | --- |
| AI Clothes Virtual Try-On V2.0 | 2 |
| AI Clothes Virtual Try-On V3.0 | 2 |

**V4.0 is not listed.** The docs do not state a unit cost for the engine we are
calling. `GET /s2s/v2.0/credit/feature-cost` returns per-SKU costs keyed by
`run_task_url` and is the documented way to look this up at runtime; it is wired
in the client but not surfaced in the UI yet.

Reference: the hackathon landing page states every registered participant
receives **1,000 free API units**. "Units" are the vendor's billing currency and
are also referred to as "Credit" in the Unit System docs. Units are deducted only
when a task reaches `success`.

---

## 10. Gaps and inconsistencies found in the documentation

Reported rather than guessed around:

1. **V4.0 unit cost is undocumented.** Only V2.0 and V3.0 (2 units) appear in the
   table. Resolve at runtime via `/s2s/v2.0/credit/feature-cost`.
2. **`FileResponseV2` schema is malformed.** It declares `"data": null` next to a
   `$ref`, contradicting its own `curl` sample. We accept both nestings.
3. **Minimum image size contradicts itself.** AI Clothes File Specs say
   "long side at least 128 pixels"; the general Error Codes page says
   `error_below_min_image_size` means "at least 320 pixels". We do not enforce
   either client-side and surface the server's own message instead.
4. **Target user image guidance conflicts.** The integration guide says "Upload a
   high-resolution full-body photo"; the File Specs table says "upper body only,
   from the chest upwards". We pass both images through unmodified and let the
   engine decide, and surface its error verbatim if it rejects either.
5. **`requests[].headers` mixes types.** The File Management schema example shows
   `"Content-Length": 50000` as a number, the integration guide shows
   `"547541"` as a string. Values are stringified before the presigned upload.
6. **Legacy credit endpoint unusable with an API key.**
   `GET /s2s/v1.0/client/credit` uses scheme `BearerAuthentication`, described as
   an `access_token` "obtained from authentication" — a v1 flow whose
   authentication endpoint is not part of the v2 documentation set we hold. Not
   implemented.
7. **Webhook completion not yet configured.** The docs call webhooks the
   preferred path. Polling is documented as the supported alternative and is what
   this phase implements.

---

## 11. Result URL lifetime — not addressed in this phase

The result URL is a presigned S3 URL **valid for 2 hours**. This phase:

- displays the URL directly in the browser;
- does **not** download, copy, cache or persist the result image;
- does **not** store the `task_id` after the response is sent;
- does **not** re-fetch or refresh an expired URL.

Consequence: if a user reloads the demo page after two hours, the image is gone.
Fixing this requires either persisting the generated image into our own storage or
retaining the `task_id` and re-polling to mint a fresh URL. Both are explicitly
out of scope for this phase and are listed as blockers in the README.
