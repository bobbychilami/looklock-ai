"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Depends

from app.catalog.providers.base import ProductProvider
from app.catalog.service import get_product_source
from app.core.config import Settings, get_settings
from app.services.youcam import YouCamService, get_youcam_service


def settings_dependency() -> Settings:
    return get_settings()


def catalog_provider_dependency(
    settings: Settings = Depends(settings_dependency),
) -> ProductProvider:
    """The catalogue provider for this request.

    A separate function rather than using `get_product_source` directly, because
    that one takes an optional `Settings` for callers outside HTTP - and FastAPI
    would try to satisfy that parameter from the request, turning every catalogue
    call into a 422. Here the settings come from the explicit `Depends`, so the
    provider follows the same configuration as everything else in the app and stays
    overridable in tests.
    """
    return get_product_source(settings)


def youcam_service_dependency(
    service: YouCamService = Depends(get_youcam_service),
) -> YouCamService:
    return service
