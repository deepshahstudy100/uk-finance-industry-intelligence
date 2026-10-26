"""Runtime configuration. All values come from environment variables (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="UKINTEL_", extra="ignore")

    # Storage. PostgreSQL is the production target; SQLite is supported for tests and quick local runs.
    database_url: str = "sqlite:///./ukintel.db"

    # Identify ourselves to public APIs. ONS asks bots for a name/version plus an organisational
    # contact URL or email (https://developer.ons.gov.uk/bots/). Do not put personal data here.
    user_agent: str = "UKIntelPlatform/0.1.0 (+https://github.com/deepshahstudy100/uk-finance-industry-intelligence)"

    # Demo mode:
    #   off       - never serve sample data; empty panels show "unavailable".
    #   fallback  - serve clearly labelled sample data ONLY for series that have no real observations.
    #   only      - serve sample data everywhere (offline UI development). Always labelled.
    demo_mode: Literal["off", "fallback", "only"] = "fallback"

    # Optional free keys. Core operation never requires them.
    companies_house_api_key: str | None = None  # free registration at developer.company-information.service.gov.uk
    nomis_uid: str | None = None  # optional; lifts the 25,000-cell guest limit

    # BoE spot FX (XUDL*) may contain third-party (LSEG/Bloomberg) content excluded from OGL.
    # Disabled by default; ECB reference rates are used instead. Enable only if your use is permitted.
    enable_boe_fx: bool = False

    http_timeout_s: float = 45.0
    http_max_attempts: int = 4
    cache_dir: str = "./.cache"

    cors_origins: str = "http://localhost:3000"
    # If set, POST endpoints that trigger ingestion require header X-Admin-Token with this value.
    admin_token: str | None = None
    scheduler_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
