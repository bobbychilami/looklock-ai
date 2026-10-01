"""Behaviour tests for the YouCam HTTP client, driven by a mock transport.

No real API key and no network access are involved.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.services.youcam.client import YouCamClient
from app.services.youcam.errors import (
    YouCamAuthError,
    YouCamError,
    YouCamNotConfiguredError,
    YouCamRateLimitError,
    YouCamTaskError,
    YouCamTimeoutError,
)

API_KEY = "test-key-not-real"
BASE_URL = "https://yce-api-01.makeupar.com"
CLOTH_PATH = "/s2s/v2.0/task/cloth-v4"


def _settings(**overrides) -> Settings:
    return Settings(
        youcam_api_key=API_KEY,
        youcam_api_base_url=BASE_URL,
        **overrides,
    )


def _client(handler, **overrides) -> YouCamClient:
    client = YouCamClient(_settings(**overrides), transport=httpx.MockTransport(handler))

    async def _no_sleep(*_args, **_kwargs) -> None:
        return None

    client._sleep_before_retry = _no_sleep  # type: ignore[method-assign]
    return client


async def test_missing_api_key_fails_before_any_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be issued without an API key")

    client = YouCamClient(
        Settings(youcam_api_key=None), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(YouCamNotConfiguredError):
        await client.get_feature_cost()


async def test_bearer_header_is_attached() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"status": 200, "result": {"skus": []}})

    client = _client(handler)
    try:
        await client.get_feature_cost()
    finally:
        await client.aclose()

    assert seen["authorization"] == f"Bearer {API_KEY}"


async def test_401_maps_to_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"status": 401, "error": "Invalid API key"})

    client = _client(handler)
    try:
        with pytest.raises(YouCamAuthError):
            await client.create_file_upload(file_name="a.jpg", file_size=10)
    finally:
        await client.aclose()


async def test_429_retries_three_times_then_raises() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(429, json={"status": 429, "error": "Too many requests"})

    client = _client(handler)
    try:
        with pytest.raises(YouCamRateLimitError):
            await client.get_feature_cost()
    finally:
        await client.aclose()

    assert calls["count"] == 3


async def test_task_submission_and_polling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert json.loads(request.content)["src_file_id"] == "f1"
            return httpx.Response(200, json={"status": 200, "data": {"task_id": "task-123"}})
        return httpx.Response(
            200,
            json={
                "status": 200,
                "data": {
                    "task_status": "success",
                    "results": {"url": "https://example.com/r.jpg"},
                },
            },
        )

    client = _client(handler)
    try:
        submitted = await client.run_task(CLOTH_PATH, {"src_file_id": "f1"})
        assert submitted.task_id == "task-123"

        finished = await client.await_task(CLOTH_PATH, "task-123")
        assert finished.data is not None
        assert finished.data.results is not None
        assert finished.data.results.url == "https://example.com/r.jpg"
    finally:
        await client.aclose()


async def test_terminal_task_error_carries_engine_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": 200, "data": {"task_status": "error", "error": "error_no_face"}},
        )

    client = _client(handler)
    try:
        with pytest.raises(YouCamTaskError) as excinfo:
            await client.await_task("/s2s/v2.0/task/skin-analysis", "t1")
    finally:
        await client.aclose()

    assert excinfo.value.error_code == "error_no_face"


async def test_poll_budget_is_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": 200, "data": {"task_status": "running"}})

    client = _client(
        handler,
        youcam_poll_interval_seconds=0,
        youcam_poll_timeout_seconds=0,
    )
    try:
        with pytest.raises(YouCamTimeoutError):
            await client.await_task("/s2s/v2.0/task/skin-analysis", "t1")
    finally:
        await client.aclose()


async def test_file_upload_pushes_bytes_to_presigned_url() -> None:
    from app.services.youcam.service import YouCamService

    puts: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "storage.example.com":
            puts.append(request.content)
            return httpx.Response(200, json={})
        return httpx.Response(
            200,
            json={
                "status": 200,
                "data": {
                    "files": [
                        {
                            "file_id": "file-abc",
                            "requests": [
                                {
                                    "url": "https://storage.example.com/upload",
                                    "method": "PUT",
                                    "headers": {"Content-Type": "image/jpg"},
                                }
                            ],
                        }
                    ]
                },
            },
        )

    client = _client(handler)
    try:
        service = YouCamService(client)
        uploaded = await service.upload_image(b"binary-image-bytes", file_name="me.jpg")

        assert uploaded.file_id == "file-abc"
        assert puts == [b"binary-image-bytes"]
    finally:
        await client.aclose()


async def test_upload_rejects_oversized_image() -> None:
    from app.services.youcam.service import MAX_IMAGE_BYTES, YouCamService

    client = _client(lambda request: httpx.Response(200, json={}))
    try:
        service = YouCamService(client)
        with pytest.raises(YouCamError):
            await service.upload_image(b"0" * (MAX_IMAGE_BYTES + 1))
    finally:
        await client.aclose()
