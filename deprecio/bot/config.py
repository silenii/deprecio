"""Configuration settings for the Deprecio application.

All settings are loaded exclusively from environment variables (or .env file).
Split into logical groups:
  - BotSettings      — Telegram bot token and admin
  - ScraperSettings  — timeouts, rate limits, TTL for external sources
  - CacheSettings    — paths for disk cache and snapshots
  - LogSettings      — log level, format, output file
  - AppSettings      — composite root config (bot + scraper + cache + log)
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    case_sensitive=False,
)


class BotSettings(BaseSettings):
    """Telegram bot credentials."""

    model_config = _BASE_CONFIG

    bot_token: str = Field(
        ...,
        validation_alias="DEPRECIO_BOT_TOKEN",
        description="Telegram bot token from @BotFather",
    )
    admin_id: int | None = Field(None, validation_alias="ADMIN_ID")


class ScraperSettings(BaseSettings):
    """External data-source timeouts and rate limiting."""

    model_config = _BASE_CONFIG

    avito_max_pages: int = Field(3, validation_alias="AVITO_MAX_PAGES", ge=1, le=20)
    snapshot_ttl_hours: int = Field(24, validation_alias="SNAPSHOT_TTL_HOURS", ge=1)
    gsmarena_timeout_sec: float = Field(10.0, validation_alias="GSMARENA_TIMEOUT", gt=0)
    avito_timeout_sec: float = Field(15.0, validation_alias="AVITO_TIMEOUT", gt=0)
    price_lookup_timeout_sec: float = Field(8.0, validation_alias="PRICE_LOOKUP_TIMEOUT", gt=0)

    # Max requests per minute to each external host (0 = no limit)
    avito_rate_limit_rpm: int = Field(30, validation_alias="AVITO_RATE_LIMIT_RPM", ge=0)
    gsmarena_rate_limit_rpm: int = Field(20, validation_alias="GSMARENA_RATE_LIMIT_RPM", ge=0)

    # Retry settings for transient network errors
    external_retry_attempts: int = Field(2, validation_alias="EXTERNAL_RETRY_ATTEMPTS", ge=0, le=5)
    external_retry_delay_sec: float = Field(1.0, validation_alias="EXTERNAL_RETRY_DELAY", gt=0)


class CacheSettings(BaseSettings):
    """Filesystem paths for local disk caches."""

    model_config = _BASE_CONFIG

    cache_dir: Path = Field(Path(".cache/devices"), validation_alias="CACHE_DIR")
    snapshot_dir: Path = Field(Path(".cache/snapshots"), validation_alias="SNAPSHOT_DIR")
    catalog_file: Path = Field(Path("data/catalog.json"), validation_alias="CATALOG_FILE")
    global_db_file: Path = Field(Path("data/global_devices.db"), validation_alias="GLOBAL_DB_FILE")

    @field_validator("cache_dir", "snapshot_dir", mode="after")
    @classmethod
    def _ensure_dir(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


class LogSettings(BaseSettings):
    """Logging configuration."""

    model_config = _BASE_CONFIG

    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field("plain", validation_alias="LOG_FORMAT")
    log_file: str = Field("", validation_alias="LOG_FILE")
    @field_validator("log_level", mode="after")
    @classmethod
    def _validate_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}, got {v!r}")
        return upper

    @field_validator("log_format", mode="after")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        if v.lower() not in {"plain", "json"}:
            raise ValueError(f"LOG_FORMAT must be 'plain' or 'json', got {v!r}")
        return v.lower()


class AppSettings(BaseSettings):
    """Composite application settings — single root object for easy DI."""

    model_config = _BASE_CONFIG

    # Telegram
    bot_token: str = Field(
        ...,
        validation_alias="DEPRECIO_BOT_TOKEN",
        description="Telegram bot token from @BotFather",
    )
    admin_id: int | None = Field(None, validation_alias="ADMIN_ID")

    # Scraper / external sources
    avito_max_pages: int = Field(3, validation_alias="AVITO_MAX_PAGES", ge=1, le=20)
    snapshot_ttl_hours: int = Field(24, validation_alias="SNAPSHOT_TTL_HOURS", ge=1)
    gsmarena_timeout_sec: float = Field(10.0, validation_alias="GSMARENA_TIMEOUT", gt=0)
    avito_timeout_sec: float = Field(15.0, validation_alias="AVITO_TIMEOUT", gt=0)
    price_lookup_timeout_sec: float = Field(8.0, validation_alias="PRICE_LOOKUP_TIMEOUT", gt=0)
    avito_rate_limit_rpm: int = Field(30, validation_alias="AVITO_RATE_LIMIT_RPM", ge=0)
    gsmarena_rate_limit_rpm: int = Field(20, validation_alias="GSMARENA_RATE_LIMIT_RPM", ge=0)
    external_retry_attempts: int = Field(2, validation_alias="EXTERNAL_RETRY_ATTEMPTS", ge=0, le=5)
    external_retry_delay_sec: float = Field(1.0, validation_alias="EXTERNAL_RETRY_DELAY", gt=0)

    # Cache / filesystem
    cache_dir: Path = Field(Path(".cache/devices"), validation_alias="CACHE_DIR")
    snapshot_dir: Path = Field(Path(".cache/snapshots"), validation_alias="SNAPSHOT_DIR")
    catalog_file: Path = Field(Path("data/catalog.json"), validation_alias="CATALOG_FILE")
    global_db_file: Path = Field(Path("data/global_devices.db"), validation_alias="GLOBAL_DB_FILE")

    # Logging
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field("plain", validation_alias="LOG_FORMAT")
    log_file: str = Field("", validation_alias="LOG_FILE")
    price_alert_check_interval_sec: int = Field(3600, validation_alias="PRICE_ALERT_CHECK_INTERVAL_SEC", gt=0)
    price_alert_max_per_user: int = Field(20, validation_alias="PRICE_ALERT_MAX_PER_USER", gt=0)

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls()

    # ------------------------------------------------------------------ #
    # Backward-compat shim: old code used BotConfig.from_env()
    # ------------------------------------------------------------------ #


# Keep BotConfig as a thin alias so existing imports don't break
BotConfig = AppSettings
