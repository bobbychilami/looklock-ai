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


def _present(value: object) -> bool:
    """True when a setting was supplied as something other than blank.

    Environment files and CI both deliver empty strings for "unset", and treating
    those as present would report a misconfigured deployment as ready.
    """
    return isinstance(value, str) and bool(value.strip())


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

    # --- Product providers ---
    # Which provider the app treats as the live catalogue. `shopping` is the
    # India-first live Google Shopping source via SerpApi and is the default. The
    # bundled fictional demo catalogue is no longer selectable, so an unconfigured
    # deployment reports "no live catalogue available" instead of serving invented
    # products while looking configured.
    #
    # There is deliberately no `auto`: make the choice explicit.
    product_provider: str = "shopping"

    # --- Amazon Creators API (official PA-API successor) ---
    # Documented at
    # https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction
    #
    # Access requires an enrolled Associates account, registered API access and
    # qualifying sales, so a fresh environment almost always starts with this off.
    amazon_enabled: bool = False
    # IN marketplace per the locale reference. Held as config because the same
    # credentials can serve other locales, and because the product ids and the
    # currency the engine compares depend on it.
    amazon_marketplace: str = "www.amazon.in"
    amazon_partner_tag: str | None = None
    amazon_client_id: str | None = None
    amazon_client_secret: str | None = None
    # Regional token host. India is served by the Europe region.
    amazon_token_url: str = "https://api.amazon.co.uk/auth/o2/token"
    amazon_catalog_url: str = "https://creatorsapi.amazon"
    amazon_timeout_seconds: float = 15.0
    # `SearchItems` returns at most ten items per request and throttles repeated
    # calls, so responses are memoised briefly and searches are capped.
    amazon_cache_ttl_seconds: float = 300.0
    amazon_search_page_size: int = 10
    #: How many distinct queries one recommendation round may issue.
    amazon_max_queries_per_request: int = 6


    # --- SerpApi Google Shopping ---
    serpapi_enabled: bool = True
    serpapi_api_key: str | None = None
    serpapi_location: str = 'India'
    serpapi_gl: str = 'in'
    serpapi_hl: str = 'en'
    serpapi_country: str = 'IN'
    serpapi_cache_ttl_seconds: int = 1800
    serpapi_timeout_seconds: float = 15.0
    serpapi_max_queries_per_request: int = 3
    serpapi_search_engine: str = 'google_shopping'
    serpapi_monthly_search_limit: int = 100
    # --- Cached feature availability ---
    @property
    def youcam_is_configured(self) -> bool:
        """True when an API key is present. Used to gate integration routes."""
        return bool(self.youcam_api_key and self.youcam_api_key.strip())

    @property
    def amazon_is_configured(self) -> bool:
        """True when every credential the Creators API needs is present.

        Checked as a set rather than a single flag so `/status` can tell a shopper
        - and whoever is deploying this - precisely which values are missing
        instead of a generic "not configured".
        """
        return not self.amazon_missing_settings

    @property
    def amazon_missing_settings(self) -> tuple[str, ...]:
        """Names of the settings `amazon_is_configured` needs and did not find.

        Reported by name on purpose. The alternative - a boolean - forces the
        operator to guess which of four values to go and create.

        `AMAZON_ENABLED` is only reported once the credentials are present, so a
        default checkout is told "enable it" rather than handed four blanks to
        fill in before it could work anyway.
        """
        credentials = {
            "AMAZON_CLIENT_ID": self.amazon_client_id,
            "AMAZON_CLIENT_SECRET": self.amazon_client_secret,
            "AMAZON_PARTNER_TAG": self.amazon_partner_tag,
        }
        absent = tuple(sorted(name for name, value in credentials.items() if not _present(value)))
        if not absent and not self.amazon_enabled:
            return ("AMAZON_ENABLED",)
        return absent


    @property
    def serpapi_is_configured(self) -> bool:
        return bool(self.serpapi_api_key and self.serpapi_api_key.strip() and self.serpapi_enabled)

    @property
    def serpapi_missing_settings(self) -> tuple[str, ...]:
        absent: list[str] = []
        if not self.serpapi_enabled:
            absent.append('SERPAPI_ENABLED')
        if not (self.serpapi_api_key and self.serpapi_api_key.strip()):
            absent.append('SERPAPI_API_KEY')
        return tuple(absent)
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
