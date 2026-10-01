"""Smoke tests for the scaffold: health probes and integration status.

No network calls are made. YouCam response parsing is covered separately in
`test_youcam_schemas.py`.

The `settings_dependency` override is load-bearing. `Settings` reads the repo's
`.env` and the ambient environment, so on a machine that has a real
`YOUCAM_API_KEY` configured these probes would otherwise report "configured" and
these tests would fail for reasons that have nothing to do with the code. Both
states are asserted explicitly instead.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import settings_dependency
from app.core.config import Settings
from app.main import create_app

API_KEY = "test-key-not-real"


def _app(*, api_key: str | None) -> FastAPI:
    app = create_app()
    app.dependency_overrides[settings_dependency] = lambda: Settings(
        youcam_api_key=api_key
    )
    return app


@pytest.fixture(params=[None, API_KEY], ids=["no_key", "with_key"])
def any_key_app(request: pytest.FixtureRequest) -> FastAPI:
    """An app that works whether or not a real key happens to be present."""
    return _app(api_key=request.param)


def test_health_reports_ok_whatever_the_ambient_key_is(any_key_app: FastAPI) -> None:
    with TestClient(any_key_app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "youcam_configured" in response.json()


def test_health_never_exposes_credentials() -> None:
    for api_key in (None, API_KEY):
        with TestClient(_app(api_key=api_key)) as client:
            response = client.get("/api/v1/health")
        assert "youcam_api_key" not in response.text
        assert "YOUCAM_API_KEY" not in response.text


def test_ready_is_degraded_without_a_key() -> None:
    with TestClient(_app(api_key=None)) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["youcam_configured"] is False
    assert body["status"] == "degraded"


def test_ready_is_ok_with_a_key() -> None:
    with TestClient(_app(api_key=API_KEY)) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["youcam_configured"] is True
    assert body["status"] == "ready"


def test_integration_status_lists_features() -> None:
    with TestClient(_app(api_key=None)) as client:
        response = client.get("/api/v1/integration/ycam/status")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    names = {feature["name"] for feature in body["features"]}
    assert {"file_upload", "skin_analysis", "apparel_virtual_try_on"} <= names
