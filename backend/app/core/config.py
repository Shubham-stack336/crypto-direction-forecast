from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


def normalize_database_url(url: str) -> str:
    """Accept postgres:// and postgresql:// (as hosting providers hand out) and force psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    """All configuration comes from APP_* environment variables (or a local .env)."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    environment: str = "development"
    model_dir: Path = BASE_DIR / "artifacts"
    exchange_id: str = "binance"
    market_timeout_ms: int = Field(10_000, ge=1_000, le=60_000)
    market_max_retries: int = Field(3, ge=1, le=5)
    market_candles_limit: int = Field(500, ge=150, le=1000)
    max_staleness_candles: int = Field(3, ge=1, le=48)
    cors_origins: list[str] = Field(default_factory=list)

    database_url: str | None = None
    db_connect_timeout_s: int = Field(5, ge=1, le=30)
    db_statement_timeout_ms: int = Field(5_000, ge=100, le=60_000)
    db_pool_size: int = Field(5, ge=1, le=20)

    @field_validator("model_dir")
    @classmethod
    def resolve_model_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else BASE_DIR / value

    @field_validator("database_url")
    @classmethod
    def clean_database_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_database_url(value.strip())

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("APP_CORS_ORIGINS must list explicit origins, not '*'")
        return value

    @model_validator(mode="after")
    def production_requires_database(self) -> "Settings":
        if self.environment == "production" and not self.database_url:
            raise ValueError("APP_DATABASE_URL is required when APP_ENVIRONMENT=production")
        return self

    @property
    def json_logs(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
