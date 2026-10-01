"""Application configuration.

All secrets are read from environment variables (or a local `.env` file at the
repository root). Nothing here is ever returned by an HTTP route.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
ROOT_ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime settings for the LOOKLOCK AI backend."""

    model_config = SettingsConfigDict(
        env_file=(ROOT_ENV_FILE, BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "LOOKLOCK AI API"
    app_env: str = "development"
    log_level: str = "INFO"

    # --- CORS ---
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- YouCam API (Perfect Corp) ---
    # Base host per docs: https://docs.makeupar.com/develop/api_server
    youcam_api_base_url: str = "https://yce-api-01.makeupar.com"

    # The vendor is "YouCam", so `YOUCAM_API_KEY` is the canonical spelling.
    # `YOUTCAM_API_KEY` is accepted as an alias because the hackathon brief uses
    # it; both map to this one field and neither value is ever returned by a route.
    youcam_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("youcam_api_key", "youtcam_api_key"),
    )

    youcam_timeout_seconds: float = 60.0

    # Docs suggest polling "every 10 seconds or so". We use 5s so the demo feels
    # responsive; the value is configuration, not a protocol requirement.
    youcam_poll_interval_seconds: float = 5.0
    youcam_poll_timeout_seconds: float = 180.0

    # How long a finished try-on job stays readable. Only affects how long the
    # demo can keep polling our own status endpoint; nothing is persisted.
    youcam_tryon_job_ttl_seconds: float = 900.0

    # --- Cached feature availability ---
    @property
    def youcam_is_configured(self) -> bool:
        """True when an API key is present. Used to gate integration routes."""
        return bool(self.youcam_api_key and self.youcam_api_key.strip())

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow `CORS_ORIGINS=a,b` as well as a real JSON list."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (FastAPI dependency)."""
    return Settings()
