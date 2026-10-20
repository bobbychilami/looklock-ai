"""Tests for the AI Clothes Virtual Try-On V4.0 proof of concept.

Everything runs against an in-process mock transport, so no API key and no
network access are involved. The request shapes asserted here are the ones
transcribed in `docs/YOUTCAM_VTO_PROOF.md`.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import youcam_service_dependency
from app.api.routes.tryon import router as tryon_router
from app.core.config import Settings
from app.core.image_validation import ImageValidationError, validate_image
from app.main import create_app
from app.services.tryon import (
    PHASE_SEQUENCE,
    TryOnJob,
    TryOnPhase,
    TryOnReference,
    TryOnRunner,
    get_tryon_job_store,
    reset_tryon_jobs,
)
from app.services.youcam.client import YouCamClient
from app.services.youcam.errors import YouCamTaskError
from app.services.youcam.schemas import ClothV4TaskRequest
from app.services.youcam.service import YouCamService

API_KEY = "test-key-not-real"
BASE_URL = "https://yce-api-01.makeupar.com"
CLOTH_PATH = "/s2s/v2.0/task/cloth-v4"

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"looklock" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"looklock" * 32


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


class AsyncMockTransport(httpx.AsyncBaseTransport):
    """`httpx.MockTransport` with an awaitable handler.

    The stock version only supports a synchronous handler, which means a mock
    server can never suspend. Being able to `await` inside the handler is what
    lets these tests observe the real intermediate phases of a background job.
    """

    def __init__(self, handler) -> None:
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._handler(request)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError("the YouCam client must use its async path")


class VendorRecorder:
    """Mock YouCam server that records the exact requests it was sent."""

    def __init__(
        self,
        *,
        poll_statuses: list[str] | None = None,
        yield_delay: float = 0.0,
    ) -> None:
        self.poll_statuses = poll_statuses or ["running", "success"]
        #: Seconds to suspend inside each handler call, so a background job really
        #: yields and its intermediate phases can be observed from a poll.
        self.yield_delay = yield_delay
        self.file_requests: list[dict] = []
        self.task_bodies: list[dict] = []
        self.uploads: list[tuple[str, bytes, dict[str, str]]] = []
        self.status_calls = 0
        self._file_seq = 0
        self._task_id = "task-vto-1"
        self._result_url = "https://storage.example.com/result.jpg?sig=x"
        self._file_api_status = 200
        self._task_api_status = 200
        self._error_code = "error_invalid_ref"

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if self.yield_delay:
            await asyncio.sleep(self.yield_delay)

        if request.url.host == "storage.example.com":
            assert request.method == "PUT"
            assert "authorization" not in request.headers, (
                "the presigned upload must never receive the YouCam API key"
            )
            self.uploads.append((str(request.url), request.content, dict(request.headers)))
            return httpx.Response(200, json={})

        if request.method == "POST" and request.url.path == "/s2s/v2.0/file":
            assert request.headers["authorization"] == f"Bearer {API_KEY}"
            body = json.loads(request.content)
            self.file_requests.append(body)
            if self._file_api_status != 200:
                return httpx.Response(
                    self._file_api_status,
                    json={"status": self._file_api_status, "error": "boom"},
                )
            self._file_seq += 1
            return httpx.Response(200, json=self._file_descriptor(self._file_seq))

        if request.method == "POST" and request.url.path == CLOTH_PATH:
            assert request.headers["authorization"] == f"Bearer {API_KEY}"
            self.task_bodies.append(json.loads(request.content))
            if self._task_api_status != 200:
                return httpx.Response(
                    self._task_api_status,
                    json={
                        "status": self._task_api_status,
                        "error": "The operation could not be completed",
                        "error_code": "InvalidParameters",
                    },
                )
            return httpx.Response(
                200, json={"status": 200, "data": {"task_id": self._task_id}}
            )

        if request.method == "GET" and request.url.path.startswith(CLOTH_PATH):
            state = self.poll_statuses[min(self.status_calls, len(self.poll_statuses) - 1)]
            self.status_calls += 1
            if state == "success":
                data = {"task_status": "success", "results": {"url": self._result_url}}
            elif state == "error":
                data = {
                    "task_status": "error",
                    "error": self._error_code,
                    "error_message": self.error_message,
                }
            else:
                data = {"task_status": "running"}
            return httpx.Response(200, json={"status": 200, "data": data})

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    def _file_descriptor(self, seq: int) -> dict:
        return {
            "status": 200,
            "data": {
                "files": [
                    {
                        "content_type": "image/jpg",
                        "file_name": f"looklock-{seq}.jpg",
                        "file_id": f"file-{seq}",
                        "requests": [
                            {
                                "url": f"https://storage.example.com/upload/{seq}",
                                "method": "PUT",
                                # Deliberately an int: the published example mixes
                                # int and str here, and both must work.
                                "headers": {
                                    "Content-Type": "image/jpg",
                                    "Content-Length": 100,
                                },
                            }
                        ],
                    }
                ]
            },
        }

    error_message = "The reference garment was rejected."


def _service(recorder: VendorRecorder, *, api_key: str | None = API_KEY) -> YouCamService:
    settings = Settings(
        youcam_api_key=api_key,
        youcam_api_base_url=BASE_URL,
        youcam_poll_interval_seconds=0,
        youcam_poll_timeout_seconds=5,
    )
    return YouCamService(YouCamClient(settings, transport=AsyncMockTransport(recorder.handler)))


def _app(service: YouCamService) -> FastAPI:
    app = create_app()
    app.include_router(tryon_router, prefix="/api/v1")
    app.dependency_overrides[youcam_service_dependency] = lambda: service
    store = get_tryon_job_store(Settings(youcam_tryon_job_ttl_seconds=60))
    store.clear()
    app.dependency_overrides[get_tryon_job_store] = lambda: store
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


def _files(source: bytes = JPEG_BYTES, reference: bytes = PNG_BYTES) -> dict:
    return {
        "source_image": ("me.jpg", source, "image/jpeg"),
        "reference_image": ("garment.png", reference, "image/png"),
    }


async def _wait_for_terminal(
    client: httpx.AsyncClient, job_id: str, *, attempts: int = 200
) -> dict:
    body: dict = {}
    for _ in range(attempts):
        response = await client.get(f"/api/v1/integration/ycam/vto/test/{job_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        if body["phase"] in {"completed", "failed"}:
            return body
        await asyncio.sleep(0.001)
    raise AssertionError(f"job {job_id} never reached a terminal phase (last: {body})")


# --------------------------------------------------------------------------- #
# Request model: the documented V4.0 shape
# --------------------------------------------------------------------------- #


def test_cloth_v4_request_requires_exactly_one_source_and_reference() -> None:
    ok = ClothV4TaskRequest(src_file_id="a", ref_file_id="b")
    assert ok.garment_category == "auto"
    assert ok.filter_multi_person == "off"
    assert ok.change_shoes is True

    with pytest.raises(ValueError):
        ClothV4TaskRequest(src_file_id="a", src_file_url="http://x", ref_file_id="b")
    with pytest.raises(ValueError):
        ClothV4TaskRequest(src_file_id="a")
    with pytest.raises(ValueError):
        ClothV4TaskRequest()


def test_cloth_v4_request_rejects_undocumented_values() -> None:
    with pytest.raises(ValueError):
        ClothV4TaskRequest(src_file_id="a", ref_file_id="b", garment_category="hat")
    with pytest.raises(ValueError):
        ClothV4TaskRequest(src_file_id="a", ref_file_id="b", filter_multi_person="yes")
    # V4.0 has no template variant; an unknown field must not be forwarded.
    with pytest.raises(ValueError):
        ClothV4TaskRequest(src_file_id="a", ref_file_id="b", template_id="t1")


async def test_submit_sends_exact_documented_v4_body() -> None:
    recorder = VendorRecorder()
    service = _service(recorder)
    try:
        task_id = await service.submit_try_on_garment(
            source_file_id="file-1",
            reference_file_id="file-2",
            garment_category="full_body",
            filter_multi_person="strict",
        )
    finally:
        await service.client.aclose()

    assert task_id == "task-vto-1"
    assert recorder.task_bodies == [
        {
            "src_file_id": "file-1",
            "ref_file_id": "file-2",
            "garment_category": "full_body",
            "filter_multi_person": "strict",
            "change_shoes": True,
        }
    ]


# --------------------------------------------------------------------------- #
# Image validation (runs before any vendor call)
# --------------------------------------------------------------------------- #


def test_validation_accepts_jpeg_and_png_and_normalises_content_type() -> None:
    jpeg = validate_image(JPEG_BYTES, label="your photo", declared_content_type="image/jpg")
    assert jpeg.content_type == "image/jpg"
    png = validate_image(PNG_BYTES, label="garment", declared_content_type="image/png")
    assert png.content_type == "image/png"


@pytest.mark.parametrize(
    "data,declared,expected",
    [
        (b"", "image/jpeg", "No data was received"),
        (b"GIF89a" + b"0" * 32, "image/gif", "not a supported image type"),
        (b"not-an-image" * 8, "image/jpeg", "is not a JPEG or PNG image"),
        (b"\xff\xd8\xff\xe0" + b"0" * 32, "image/png", "but its contents look like"),
    ],
)
def test_validation_rejects_bad_payloads(data: bytes, declared: str, expected: str) -> None:
    with pytest.raises(ImageValidationError, match=expected):
        validate_image(data, label="your photo", declared_content_type=declared)


def test_validation_rejects_oversized_image() -> None:
    with pytest.raises(ImageValidationError, match="accepts at most"):
        validate_image(JPEG_BYTES, label="your photo", max_bytes=8)


# --------------------------------------------------------------------------- #
# Endpoint: happy path across all four documented steps
# --------------------------------------------------------------------------- #


async def test_end_to_end_try_on_returns_result_url() -> None:
    recorder = VendorRecorder()
    service = _service(recorder)
    async with _client(_app(service)) as client:
        try:
            response = await client.post(
                "/api/v1/integration/ycam/vto/test",
                files=_files(),
                data={"garment_category": "full_body", "filter_multi_person": "off"},
            )
            assert response.status_code == 202, response.text
            accepted = response.json()
            assert accepted["phase"] == "queued"
            assert accepted["poll_url"].endswith(accepted["job_id"])

            body = await _wait_for_terminal(client, accepted["job_id"])
        finally:
            await service.client.aclose()
            await reset_tryon_jobs()

    assert body["phase"] == "completed"
    assert body["result_url"] == recorder._result_url
    assert body["youcam_task_id"] == "task-vto-1"
    assert body["youcam_task_status"] == "success"
    assert body["error"] is None
    assert body["result_url_expires_in_hours"] == 2
    assert any("2 hours" in note for note in body["notes"])

    # Step 1 + 2: one File API call and one presigned PUT per image.
    assert len(recorder.file_requests) == 2
    assert [f["file_name"] for f in recorder.file_requests[0]["files"]] == [
        "looklock-source.jpg"
    ]
    assert [f["file_name"] for f in recorder.file_requests[1]["files"]] == [
        "looklock-reference.png"
    ]
    assert recorder.file_requests[0]["files"][0]["content_type"] == "image/jpg"
    assert recorder.file_requests[1]["files"][0]["content_type"] == "image/png"
    assert [payload for _, payload, _ in recorder.uploads] == [JPEG_BYTES, PNG_BYTES]

    # Integer header value from the vendor example is stringified on the way out.
    assert recorder.uploads[0][2]["content-length"] == "100"

    # Step 3 + 4.
    assert recorder.task_bodies[0]["src_file_id"] == "file-1"
    assert recorder.task_bodies[0]["ref_file_id"] == "file-2"
    assert recorder.task_bodies[0]["garment_category"] == "full_body"
    assert recorder.status_calls == 2  # running, then success


async def test_runner_reports_each_documented_phase_in_order() -> None:
    """Unit-level check of the phase sequence, free of polling races."""
    recorder = VendorRecorder(poll_statuses=["running", "running", "success"])
    service = _service(recorder)
    store = get_tryon_job_store(Settings(youcam_tryon_job_ttl_seconds=60))
    store.clear()
    template = store.create(garment_category="auto", filter_multi_person="off")

    phases: list[str] = []

    class RecordingJob(TryOnJob):
        def advance(self, phase: TryOnPhase) -> None:
            phases.append(phase)
            super().advance(phase)

    job = RecordingJob(
        job_id=template.job_id,
        garment_category=template.garment_category,
        filter_multi_person=template.filter_multi_person,
    )
    source = validate_image(JPEG_BYTES, label="your photo", declared_content_type="image/jpeg")
    reference = validate_image(PNG_BYTES, label="garment", declared_content_type="image/png")

    try:
        await TryOnRunner(service).run(
            job, source=source, reference=TryOnReference(image=reference)
        )
    finally:
        await service.client.aclose()
        store.clear()

    assert phases == [
        "uploading_source_image",
        "uploading_reference_image",
        "submitting_task",
        "polling_task",
    ]
    assert job.phase == "completed"
    assert job.youcam_task_status == "success"
    assert job.youcam_task_id == "task-vto-1"
    assert job.result_url == recorder._result_url


async def test_poll_reports_progress_that_never_goes_backwards() -> None:
    """The browser must see real progress, not a spinner.

    Which individual phases a given poll happens to land on is timing-dependent,
    so the guarantee asserted here is the one that actually matters: the phase
    only ever advances through `PHASE_SEQUENCE`, and the run ends `completed`.
    """
    recorder = VendorRecorder(poll_statuses=["running", "running", "success"], yield_delay=0.001)
    service = _service(recorder)
    async with _client(_app(service)) as client:
        try:
            accepted = (
                await client.post("/api/v1/integration/ycam/vto/test", files=_files())
            ).json()
            job_id = accepted["job_id"]

            observed: list[str] = []
            vendor_states: list[str | None] = []
            for _ in range(200):
                body = (
                    await client.get(f"/api/v1/integration/ycam/vto/test/{job_id}")
                ).json()
                if not observed or observed[-1] != body["phase"]:
                    observed.append(body["phase"])
                if not vendor_states or vendor_states[-1] != body["youcam_task_status"]:
                    vendor_states.append(body["youcam_task_status"])
                if body["phase"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.001)
        finally:
            await service.client.aclose()
            await reset_tryon_jobs()

    assert observed[-1] == "completed"
    indexes = [PHASE_SEQUENCE.index(phase) for phase in observed]
    assert indexes == sorted(indexes), f"phase went backwards: {observed}"
    assert observed[0] in PHASE_SEQUENCE
    assert "polling_task" in observed
    assert vendor_states[-1] == "success"
    assert "running" in vendor_states


# --------------------------------------------------------------------------- #
# Endpoint: failure modes
# --------------------------------------------------------------------------- #


async def test_engine_error_is_surfaced_with_vendor_error_code() -> None:
    recorder = VendorRecorder(poll_statuses=["error"])
    recorder._error_code = "error_invalid_ref"
    service = _service(recorder)
    async with _client(_app(service)) as client:
        try:
            accepted = (
                await client.post("/api/v1/integration/ycam/vto/test", files=_files())
            ).json()
            body = await _wait_for_terminal(client, accepted["job_id"])
        finally:
            await service.client.aclose()
            await reset_tryon_jobs()

    assert body["phase"] == "failed"
    assert body["error_code"] == "error_invalid_ref"
    assert body["error"] == "The reference garment was rejected."
    assert body["result_url"] is None


async def test_mapped_engine_error_uses_our_wording_when_vendor_omits_it() -> None:
    """Without `error_message`, the vendor's engine code drives our wording."""
    recorder = VendorRecorder(poll_statuses=["error"])

    async def async_handler(request: httpx.Request) -> httpx.Response:
        # Deliberately omits `error_message`, unlike the recorder's default.
        if request.method == "GET" and request.url.path.startswith(CLOTH_PATH):
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "data": {"task_status": "error", "error": "error_pose"},
                },
            )
        return await recorder.handler(request)

    settings = Settings(
        youcam_api_key=API_KEY,
        youcam_api_base_url=BASE_URL,
        youcam_poll_interval_seconds=0,
        youcam_poll_timeout_seconds=5,
    )
    service = YouCamService(
        YouCamClient(settings, transport=AsyncMockTransport(async_handler))
    )
    async with _client(_app(service)) as client:
        try:
            accepted = (
                await client.post("/api/v1/integration/ycam/vto/test", files=_files())
            ).json()
            body = await _wait_for_terminal(client, accepted["job_id"])
        finally:
            await service.client.aclose()
            await reset_tryon_jobs()

    assert body["error_code"] == "error_pose"
    assert "pose" in body["error"].lower()


async def test_invalid_parameters_becomes_a_failed_job() -> None:
    recorder = VendorRecorder()
    recorder._task_api_status = 400
    service = _service(recorder)
    async with _client(_app(service)) as client:
        try:
            accepted = (
                await client.post("/api/v1/integration/ycam/vto/test", files=_files())
            ).json()
            body = await _wait_for_terminal(client, accepted["job_id"])
        finally:
            await service.client.aclose()
            await reset_tryon_jobs()

    assert body["phase"] == "failed"
    assert body["error"]


async def test_bad_image_is_rejected_before_any_vendor_call() -> None:
    recorder = VendorRecorder()
    service = _service(recorder)
    async with _client(_app(service)) as client:
        try:
            response = await client.post(
                "/api/v1/integration/ycam/vto/test",
                files=_files(source=b"definitely not an image"),
            )
        finally:
            await service.client.aclose()

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_image"
    assert recorder.file_requests == []
    assert recorder.task_bodies == []


async def test_missing_api_key_returns_503_without_queueing() -> None:
    recorder = VendorRecorder()
    service = _service(recorder, api_key=None)
    async with _client(_app(service)) as client:
        response = await client.post(
            "/api/v1/integration/ycam/vto/test", files=_files()
        )

    assert response.status_code == 503
    assert response.json()["error_code"] == "youcam_not_configured"
    assert recorder.file_requests == []


async def test_unknown_job_returns_404_with_a_readable_reason() -> None:
    service = _service(VendorRecorder())
    async with _client(_app(service)) as client:
        response = await client.get("/api/v1/integration/ycam/vto/test/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error_code"] == "tryon_job_not_found"


# --------------------------------------------------------------------------- #
# Options + secret hygiene
# --------------------------------------------------------------------------- #


async def test_options_reports_the_documented_enums() -> None:
    service = _service(VendorRecorder())
    async with _client(_app(service)) as client:
        response = await client.get("/api/v1/integration/ycam/vto/options")

    assert response.status_code == 200
    body = response.json()
    assert body["youcam_endpoint"] == "POST /s2s/v2.0/task/cloth-v4"
    assert set(body["garment_categories"]) == {
        "full_body",
        "lower_body",
        "upper_body",
        "shoes",
        "auto",
        "outer",
    }
    assert body["multi_person_filters"] == ["off", "normal", "strict"]
    assert body["phases"][-1] == "completed"


async def test_no_endpoint_ever_returns_the_api_key() -> None:
    recorder = VendorRecorder()
    service = _service(recorder)
    async with _client(_app(service)) as client:
        accepted = (
            await client.post("/api/v1/integration/ycam/vto/test", files=_files())
        ).json()
        status_response = await client.get(
            f"/api/v1/integration/ycam/vto/test/{accepted['job_id']}"
        )
        await _wait_for_terminal(client, accepted["job_id"])
        options = await client.get("/api/v1/integration/ycam/vto/options")
        integration = await client.get("/api/v1/integration/ycam/status")
        health = await client.get("/api/v1/health")
        await service.client.aclose()
        await reset_tryon_jobs()

    for text in (
        accepted,
        status_response.text,
        options.text,
        integration.text,
        health.text,
    ):
        assert API_KEY not in str(text)
        assert "YOUCAM_API_KEY" not in str(text)


async def test_task_error_type_is_used_for_terminal_engine_failures() -> None:
    """Guard the exception contract the job runner relies on."""
    recorder = VendorRecorder(poll_statuses=["error"])
    settings = Settings(
        youcam_api_key=API_KEY,
        youcam_api_base_url=BASE_URL,
        youcam_poll_interval_seconds=0,
        youcam_poll_timeout_seconds=5,
    )
    service = YouCamService(
        YouCamClient(settings, transport=AsyncMockTransport(recorder.handler))
    )
    try:
        with pytest.raises(YouCamTaskError) as excinfo:
            await service.await_try_on_garment("task-vto-1")
    finally:
        await service.client.aclose()

    assert excinfo.value.error_code == "error_invalid_ref"