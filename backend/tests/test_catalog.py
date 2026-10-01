"""Tests for the catalogue, the recommendation engine, and the product try-on.

The recommendation engine is pure, so most of this file tests it directly. The
API tests run against an in-process mock transport, so no API key and no network
access are involved and the same 43 proof-of-concept tests keep passing.
"""

from __future__ import annotations

import asyncio
import json
import random
import struct
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import youcam_service_dependency
from app.api.routes.catalog import OCCASION_ORDER, STYLE_ORDER
from app.catalog import (
    ASSETS_DIR,
    Product,
    ProductImage,
    ProductSource,
    asset_path,
    get_catalogue,
    get_source,
    require_reference,
)
from app.catalog.product import ProductNotFoundError
from app.core.config import Settings
from app.core.image_validation import ValidatedImage
from app.main import create_app
from app.recommendations import (
    BUDGET_PRESETS_INR,
    LOOK_COUNT,
    MAX_BUDGET_INR,
    MIN_BUDGET_INR,
    InsufficientInventoryError,
    RecommendationRequest,
    recommend,
)
from app.services.tryon import (
    PHASE_SEQUENCE,
    TryOnJob,
    TryOnRunner,
    get_tryon_job_store,
    reset_tryon_jobs,
)
from app.services.youcam.client import YouCamClient
from app.services.youcam.service import YouCamService
from tests.test_tryon import (
    API_KEY,
    BASE_URL,
    JPEG_BYTES,
    AsyncMockTransport,
    VendorRecorder,
)

CATALOGUE = list(get_catalogue())


def _url(product: Product) -> str:
    return f"/api/v1/catalog/items/{product.product_id}/image"


def _request(**kwargs) -> RecommendationRequest:
    return RecommendationRequest(**kwargs)


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #


def test_catalogue_meets_the_documented_size_targets() -> None:
    by_slot: dict[str, int] = {}
    for product in CATALOGUE:
        by_slot[product.slot] = by_slot.get(product.slot, 0) + 1

    assert 8 <= by_slot["top"] <= 12
    assert 6 <= by_slot["bottom"] <= 10
    assert 6 <= by_slot["footwear"] + by_slot["accessory"] <= 10
    assert len(CATALOGUE) == len({p.product_id for p in CATALOGUE})


def test_every_catalogue_asset_exists_and_is_a_real_png() -> None:
    """The seed data and the generated artwork must not drift apart."""
    for product in CATALOGUE:
        path = asset_path(product)
        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{product.product_id} is not a PNG"
        # IHDR is the first chunk: length, type, then width and height.
        assert data[12:16] == b"IHDR"
        width, height = struct.unpack(">II", data[16:24])
        assert (width, height) == (1000, 1250)


def test_asset_directory_contains_no_unreferenced_images() -> None:
    """Catches artwork left behind after a catalogue edit."""
    referenced = {p.image.local_path for p in CATALOGUE}
    on_disk = {path.name for path in ASSETS_DIR.glob("*.png")}
    assert on_disk == referenced


def test_catalogue_is_demo_only_with_no_purchase_links() -> None:
    # Nothing here is a real listing, so no product may claim a shop link.
    assert all(product.purchase_url is None for product in CATALOGUE)
    assert all(product.is_demo for product in CATALOGUE)


def test_accessories_are_not_tryon_capable() -> None:
    for product in CATALOGUE:
        if product.slot == "accessory":
            assert not product.is_tryon_capable
            with pytest.raises(ProductNotFoundError):
                require_reference(product)
        else:
            assert product.is_tryon_capable


def test_tryon_capable_products_declare_a_vendor_garment_category() -> None:
    for product in CATALOGUE:
        if product.is_tryon_capable:
            assert product.garment_category in {
                "full_body",
                "lower_body",
                "upper_body",
                "shoes",
                "outer",
            }


def test_require_reference_rejects_a_product_with_no_image_at_all() -> None:
    orphan = Product(
        product_id="orphan",
        name="Orphan",
        slot="top",
        image=ProductImage(),
        price_inr=1000,
        styles=("Minimal",),
        occasions=("Casual",),
        description="No image anywhere.",
        color="None",
    )
    with pytest.raises(ProductNotFoundError):
        require_reference(orphan)


def test_offered_vocabulary_is_accepted_by_the_request_schema() -> None:
    """The onboarding UI must not be able to offer an answer the API rejects."""
    for occasion in OCCASION_ORDER:
        for style in STYLE_ORDER:
            assert _request(occasion=occasion, style=style, budget_inr=5000)
    assert list(BUDGET_PRESETS_INR) == sorted(BUDGET_PRESETS_INR)
    for preset in BUDGET_PRESETS_INR:
        assert MIN_BUDGET_INR <= preset <= MAX_BUDGET_INR


# --------------------------------------------------------------------------- #
# Recommendation engine
# --------------------------------------------------------------------------- #


def test_recommends_exactly_three_looks() -> None:
    for occasion in OCCASION_ORDER:
        for style in STYLE_ORDER:
            result = recommend(
                _request(occasion=occasion, style=style, budget_inr=25000),
                CATALOGUE,
                image_url_for=_url,
            )
            assert len(result.looks) == LOOK_COUNT
            assert [look.rank for look in result.looks] == [1, 2, 3]


def test_recommendations_are_deterministic_and_order_independent() -> None:
    request = _request(occasion="Wedding", style="Classic", budget_inr=25000)
    first = recommend(request, CATALOGUE, image_url_for=_url)
    again = recommend(request, CATALOGUE, image_url_for=_url)

    shuffled = list(CATALOGUE)
    random.Random(11).shuffle(shuffled)
    from_shuffled = recommend(request, shuffled, image_url_for=_url)

    ids = [[item.product_id for item in look.items] for look in first.looks]
    assert ids == [[item.product_id for item in look.items] for look in again.looks]
    assert ids == [[item.product_id for item in look.items] for look in from_shuffled.looks]


def test_looks_are_ranked_by_descending_score() -> None:
    result = recommend(
        _request(occasion="Wedding", style="Classic", budget_inr=25000),
        CATALOGUE,
        image_url_for=_url,
    )
    scores = [look.score.total for look in result.looks]
    assert scores == sorted(scores, reverse=True)


def test_looks_are_genuinely_different_outfits() -> None:
    """Three variations on one outfit would be a useless recommendation."""
    result = recommend(
        _request(occasion="Party", style="Modern", budget_inr=8000),
        CATALOGUE,
        image_url_for=_url,
    )
    for i, left in enumerate(result.looks):
        for right in result.looks[i + 1 :]:
            shared = {item.product_id for item in left.items} & {
                item.product_id for item in right.items
            }
            assert len(shared) <= 1, f"looks share {shared}"


def test_every_look_has_a_top_and_a_bottom() -> None:
    result = recommend(
        _request(occasion="Casual", style="Minimal", budget_inr=8000),
        CATALOGUE,
        image_url_for=_url,
    )
    for look in result.looks:
        slots = {item.slot for item in look.items}
        assert {"top", "bottom"} <= slots
        # The try-on reference is the top piece, and tops are never accessories.
        assert look.hero.slot == "top"


def test_look_total_price_is_the_sum_of_its_items() -> None:
    result = recommend(
        _request(occasion="Interview", style="Classic", budget_inr=8000),
        CATALOGUE,
        image_url_for=_url,
    )
    for look in result.looks:
        assert look.total_price_inr == sum(item.price_inr for item in look.items)


def test_budget_is_respected_when_the_catalogue_can() -> None:
    result = recommend(
        _request(occasion="Wedding", style="Classic", budget_inr=25000),
        CATALOGUE,
        image_url_for=_url,
    )
    assert all(look.total_price_inr <= 25000 for look in result.looks)
    assert result.relaxed_constraints == ()
    assert result.notice is None


def test_impossible_budget_relaxes_and_says_so() -> None:
    result = recommend(
        _request(occasion="Wedding", style="Classic", budget_inr=MIN_BUDGET_INR),
        CATALOGUE,
        image_url_for=_url,
    )
    assert len(result.looks) == LOOK_COUNT
    assert "budget" in result.relaxed_constraints
    assert result.notice is not None
    assert "₹" in result.notice
    # A relaxed result must still be the closest match available, not a random one.
    assert all(look.score.occasion >= 0.5 for look in result.looks)


def test_over_budget_looks_prefer_the_cheapest_viable_option() -> None:
    """A regression guard for the budget score saturating at zero.

    When the budget cannot be met, ranking must still put the least-over-budget
    occasion-appropriate look first rather than the most expensive one.
    """
    result = recommend(
        _request(occasion="Wedding", style="Minimal", budget_inr=MIN_BUDGET_INR),
        CATALOGUE,
        image_url_for=_url,
    )
    top = result.looks[0]
    assert top.score.occasion == 1.0
    assert top.total_price_inr == min(look.total_price_inr for look in result.looks)


def test_accessories_in_a_look_suit_the_requested_occasion() -> None:
    result = recommend(
        _request(occasion="Wedding", style="Classic", budget_inr=25000),
        CATALOGUE,
        image_url_for=_url,
    )
    for look in result.looks:
        for item in look.items:
            if item.slot == "accessory":
                assert item.matches_occasion


def test_reasons_are_built_from_real_attributes() -> None:
    result = recommend(
        _request(occasion="Wedding", style="Classic", budget_inr=25000),
        CATALOGUE,
        image_url_for=_url,
    )
    look = result.looks[0]
    assert any("wedding" in reason for reason in look.reasons)
    assert any(f"₹{look.total_price_inr:,}" in reason for reason in look.reasons)
    assert any("classic" in reason.lower() for reason in look.reasons)


def test_match_flags_reflect_the_request() -> None:
    result = recommend(
        _request(occasion="Interview", style="Minimal", budget_inr=8000),
        CATALOGUE,
        image_url_for=_url,
    )
    look = result.looks[0]
    assert all(item.matches_occasion or not item.matches_occasion for item in look.items)
    assert look.items[0].matches_style in {True, False}


def test_thin_catalogue_returns_what_it_can_with_a_notice() -> None:
    thin = [p for p in CATALOGUE if p.product_id in {"upper-ivory-shirt", "lower-ink-trousers"}]
    result = recommend(
        _request(occasion="Casual", style="Minimal", budget_inr=8000),
        thin,
        image_url_for=_url,
    )
    assert len(result.looks) == 1
    assert result.notice is not None
    assert "1" in result.notice
    assert not result.is_complete


def test_catalogue_without_a_bottom_cannot_build_a_look() -> None:
    tops_only = [p for p in CATALOGUE if p.slot == "top"]
    with pytest.raises(InsufficientInventoryError):
        recommend(
            _request(occasion="Casual", style="Minimal", budget_inr=8000),
            tops_only,
            image_url_for=_url,
        )


def test_request_rejects_out_of_range_and_unknown_values() -> None:
    with pytest.raises(ValueError):
        _request(occasion="Funeral", style="Classic", budget_inr=5000)
    with pytest.raises(ValueError):
        _request(occasion="Wedding", style="Avant-Garde", budget_inr=5000)
    with pytest.raises(ValueError):
        _request(occasion="Wedding", style="Classic", budget_inr=10)
    with pytest.raises(ValueError):
        _request(occasion="Wedding", style="Classic", budget_inr=10_000_000)
    with pytest.raises(ValueError):
        _request(occasion="Wedding", style="Classic")  # budget is required


# --------------------------------------------------------------------------- #
# HTTP: catalogue and recommendations
# --------------------------------------------------------------------------- #


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def _plain_app() -> FastAPI:
    return create_app()


async def test_catalogue_summary_endpoint() -> None:
    async with _client(_plain_app()) as client:
        response = await client.get("/api/v1/catalog/looks")
    assert response.status_code == 200
    body = response.json()
    assert body["product_count"] == len(CATALOGUE)
    assert body["counts_by_slot"]["top"] == 10
    assert body["occasions"] == list(OCCASION_ORDER)
    assert body["styles"] == list(STYLE_ORDER)
    assert body["budget_presets_inr"] == list(BUDGET_PRESETS_INR)
    assert body["is_demo_catalogue"] is True
    assert "demo" in body["notice"].lower()


async def test_catalogue_filters_combine() -> None:
    async with _client(_plain_app()) as client:
        response = await client.get(
            "/api/v1/catalog/items", params={"occasion": "Wedding", "slot": "top"}
        )
    assert response.status_code == 200
    products = response.json()["products"]
    assert products
    assert all(p["slot"] == "top" for p in products)
    assert all("Wedding" in p["occasions"] for p in products)


async def test_catalogue_rejects_an_unknown_occasion_filter() -> None:
    async with _client(_plain_app()) as client:
        response = await client.get("/api/v1/catalog/items", params={"occasion": "Funeral"})
    assert response.status_code == 422


async def test_product_image_is_served_and_unknown_products_are_not() -> None:
    async with _client(_plain_app()) as client:
        found = await client.get(f"/api/v1/catalog/items/{CATALOGUE[0].product_id}/image")
        assert found.status_code == 200
        assert found.headers["content-type"] == "image/png"
        assert found.content[:8] == b"\x89PNG\r\n\x1a\n"

        missing = await client.get("/api/v1/catalog/items/does-not-exist")
        missing_image = await client.get("/api/v1/catalog/items/does-not-exist/image")
    assert missing.status_code == 404
    assert missing_image.status_code == 404


async def test_product_image_path_cannot_be_traversed() -> None:
    async with _client(_plain_app()) as client:
        response = await client.get("/api/v1/catalog/items/..%2f..%2fconfig/image")
    assert response.status_code == 404


async def test_recommendations_endpoint_returns_three_looks() -> None:
    async with _client(_plain_app()) as client:
        response = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Wedding", "style": "Classic", "budget_inr": 25000},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["looks"]) == 3
    assert body["notice"] is None
    hero = body["looks"][0]["items"][0]
    assert hero["image_url"].endswith("/image")


async def test_recommendations_endpoint_validates_input() -> None:
    async with _client(_plain_app()) as client:
        bad_occasion = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Funeral", "style": "Classic", "budget_inr": 5000},
        )
        bad_budget = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Wedding", "style": "Classic", "budget_inr": 1},
        )
        extra_field = await client.post(
            "/api/v1/recommendations",
            json={
                "occasion": "Wedding",
                "style": "Classic",
                "budget_inr": 5000,
                "limit": 99,
            },
        )
    assert bad_occasion.status_code == 422
    assert bad_budget.status_code == 422
    assert extra_field.status_code == 422


class _TinySource:
    """A source with no bottoms, to exercise the insufficient-inventory path."""

    async def get(self, product_id: str) -> Product | None:
        return next((p for p in CATALOGUE if p.product_id == product_id), None)

    async def all(self) -> list[Product]:
        return [p for p in CATALOGUE if p.slot == "top"]

    async def search(self, query: str, **kwargs) -> tuple[Product, ...]:
        return ()


async def test_recommendations_report_a_catalogue_that_cannot_build_a_look() -> None:
    app = _plain_app()
    app.dependency_overrides[get_source] = lambda: _TinySource()
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/recommendations",
            json={"occasion": "Wedding", "style": "Classic", "budget_inr": 25000},
        )
    assert response.status_code == 409
    assert "bottom" in response.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# HTTP: product try-on
# --------------------------------------------------------------------------- #


def _service(recorder: VendorRecorder) -> YouCamService:
    settings = Settings(
        youcam_api_key=API_KEY,
        youcam_api_base_url=BASE_URL,
        youcam_poll_interval_seconds=0,
        youcam_poll_timeout_seconds=5,
    )
    return YouCamService(YouCamClient(settings, transport=AsyncMockTransport(recorder.handler)))


def _tryon_app(recorder: VendorRecorder, *, api_key: str | None = API_KEY) -> FastAPI:
    app = create_app()
    service = _service(recorder)
    if api_key is None:
        # Must be explicit: `Settings` reads the repo's real `.env` and the
        # ambient environment, so relying on "no key was passed" would quietly
        # pick up a real key on a developer machine and the 503 would never fire.
        service = YouCamService(
            YouCamClient(Settings(youcam_api_key=None, youcam_api_base_url=BASE_URL))
        )
    app.dependency_overrides[youcam_service_dependency] = lambda: service
    store = get_tryon_job_store(Settings(youcam_tryon_job_ttl_seconds=60))
    store.clear()
    app.dependency_overrides[get_tryon_job_store] = lambda: store
    return app


def _photo() -> dict:
    return {"source_image": ("me.jpg", JPEG_BYTES, "image/jpeg")}


async def _wait_for_terminal(client: httpx.AsyncClient, job_id: str) -> dict:
    body: dict = {}
    for _ in range(200):
        response = await client.get(f"/api/v1/tryon/{job_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        if body["phase"] in {"completed", "failed"}:
            return body
        await asyncio.sleep(0.001)
    raise AssertionError(f"job {job_id} never finished (last: {body})")


async def test_product_tryon_runs_to_completion() -> None:
    recorder = VendorRecorder()
    app = _tryon_app(recorder)
    product = next(p for p in CATALOGUE if p.slot == "top")

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/tryon",
            files=_photo(),
            data={"product_id": product.product_id},
        )
        assert response.status_code == 202, response.text
        accepted = response.json()
        assert accepted["product_id"] == product.product_id
        assert accepted["poll_url"].endswith(accepted["job_id"])

        final = await _wait_for_terminal(client, accepted["job_id"])

    assert final["phase"] == "completed"
    assert final["result_url"] == "https://storage.example.com/result.jpg?sig=x"
    assert final["product_name"] == product.name
    assert final["result_url_expires_in_hours"] == 2

    # The catalogue's own garment category must reach the vendor, not "auto".
    assert recorder.task_bodies[0]["garment_category"] == product.garment_category

    # And the reference we uploaded must be the catalogue asset, byte for byte.
    expected = asset_path(product).read_bytes()
    assert expected in [content for _, content, _ in recorder.uploads]


class _PhaseRecordingService:
    """A YouCam service stand-in that notes the job phase at each vendor step.

    Polling an HTTP job is inherently racy - the runner can cross several phases
    between two polls - so the phase machine is verified here instead, where the
    exact sequence is observable every time.
    """

    is_configured = True

    def __init__(self) -> None:
        self.job: TryOnJob | None = None
        self.observed: list[str] = []

    def _note(self) -> None:
        if self.job is not None:
            self.observed.append(self.job.phase)

    async def upload_image(self, data, *, file_name, content_type):
        self._note()
        return SimpleNamespace(file_id="file-1")

    async def submit_try_on_garment(self, **kwargs):
        self._note()
        return "task-1"

    async def await_try_on_garment(self, task_id, *, on_status=None):
        self._note()
        if on_status is not None:
            on_status("running")
        return SimpleNamespace(task_id=task_id, result_url="https://storage.example.com/r.jpg")


async def test_runner_walks_every_documented_phase_in_order() -> None:
    service = _PhaseRecordingService()
    job = TryOnJob(
        job_id="job-1", garment_category="upper_body", filter_multi_person="off"
    )
    service.job = job

    runner = TryOnRunner(service)  # type: ignore[arg-type]
    photo = ValidatedImage(data=JPEG_BYTES, content_type="image/jpg", size_bytes=len(JPEG_BYTES))
    garment = ValidatedImage(
        data=asset_path(CATALOGUE[0]).read_bytes(),
        content_type="image/png",
        size_bytes=100,
    )
    initial = job.phase
    await runner.run(job, source=photo, reference=garment)

    # The runner advances the phase *before* each vendor call, so recording the
    # phase at call time plus the starting and ending values reconstructs the
    # full documented walk.
    assert [initial, *service.observed, job.phase] == list(PHASE_SEQUENCE)
    assert job.result_url == "https://storage.example.com/r.jpg"
    assert job.youcam_task_id == "task-1"


async def test_product_tryon_rejects_an_unknown_product() -> None:
    app = _tryon_app(VendorRecorder())
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/tryon", files=_photo(), data={"product_id": "not-a-product"}
        )
    assert response.status_code == 404
    assert "not-a-product" in response.json()["detail"]


async def test_product_tryon_refuses_an_accessory() -> None:
    """Accessories are display-only, so this must not reach the vendor."""
    recorder = VendorRecorder()
    app = _tryon_app(recorder)
    accessory = next(p for p in CATALOGUE if p.slot == "accessory")

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/tryon", files=_photo(), data={"product_id": accessory.product_id}
        )
    assert response.status_code == 409
    assert "accessory" in response.json()["detail"].lower()
    assert recorder.task_bodies == []


async def test_product_tryon_rejects_a_non_image_upload() -> None:
    recorder = VendorRecorder()
    app = _tryon_app(recorder)
    product = next(p for p in CATALOGUE if p.slot == "top")

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/tryon",
            files={"source_image": ("notes.txt", b"not an image", "text/plain")},
            data={"product_id": product.product_id},
        )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_image"
    assert recorder.task_bodies == []


async def test_product_tryon_without_a_key_is_a_clear_503() -> None:
    app = _tryon_app(VendorRecorder(), api_key=None)
    product = next(p for p in CATALOGUE if p.slot == "top")
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/tryon", files=_photo(), data={"product_id": product.product_id}
        )
    assert response.status_code == 503
    assert response.json()["error_code"] == "youcam_not_configured"


async def test_unknown_tryon_job_is_a_404() -> None:
    app = _tryon_app(VendorRecorder())
    async with _client(app) as client:
        response = await client.get("/api/v1/tryon/does-not-exist")
    assert response.status_code == 404
    assert "nothing is persisted" in response.json()["detail"].lower()


async def test_vendor_failure_is_reported_on_the_job_not_as_a_crash() -> None:
    recorder = VendorRecorder(poll_statuses=["error"])
    app = _tryon_app(recorder)
    product = next(p for p in CATALOGUE if p.slot == "top")

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/tryon", files=_photo(), data={"product_id": product.product_id}
        )
        final = await _wait_for_terminal(client, response.json()["job_id"])

    assert final["phase"] == "failed"
    assert final["error"]
    assert final["result_url"] is None


async def test_product_tryon_never_exposes_the_api_key() -> None:
    recorder = VendorRecorder()
    app = _tryon_app(recorder)
    product = next(p for p in CATALOGUE if p.slot == "top")

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/tryon", files=_photo(), data={"product_id": product.product_id}
        )
        await _wait_for_terminal(client, response.json()["job_id"])
        status = await client.get(f"/api/v1/tryon/{response.json()['job_id']}")

    assert API_KEY not in response.text
    assert API_KEY not in status.text


async def test_the_integration_proof_of_concept_still_works() -> None:
    """The product flow must not have displaced the `/dev/vto` endpoints."""
    recorder = VendorRecorder()
    app = _tryon_app(recorder)

    async with _client(app) as client:
        options = await client.get("/api/v1/integration/ycam/vto/options")
        started = await client.post(
            "/api/v1/integration/ycam/vto/test",
            files={
                "source_image": ("me.jpg", JPEG_BYTES, "image/jpeg"),
                "reference_image": ("garment.png", b"\x89PNG\r\n\x1a\n" + b"x" * 32, "image/png"),
            },
        )

    assert options.status_code == 200
    assert "cloth-v4" in options.json()["youcam_endpoint"]
    assert started.status_code == 202
    assert json.loads(json.dumps(started.json()))["poll_url"].startswith(
        "/api/v1/integration/ycam/vto/test/"
    )


@pytest.fixture(autouse=True)
async def _clean_jobs():
    yield
    await reset_tryon_jobs()


def test_product_source_protocol_is_satisfied_by_the_static_source() -> None:
    assert isinstance(get_source(), ProductSource)
