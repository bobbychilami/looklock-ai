"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.youcam import YouCamService, get_youcam_service


def settings_dependency() -> Settings:
    return get_settings()


def youcam_service_dependency(
    service: YouCamService = Depends(get_youcam_service),
) -> YouCamService:
    return service
