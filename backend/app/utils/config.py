"""Application configuration, loaded from the repo-root `.env` file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> utils -> app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Typed view over the environment. Missing optional keys default to empty."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_publishable_key: str = ""
    supabase_jwks_url: str = ""
    database_url: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    alpha_vantage_api_key: str = ""
    newsapi_api_key: str = ""

    # Budget for any single external call, before retry.
    upstream_timeout_seconds: float = 10.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
