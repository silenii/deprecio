"""Configuration settings for the Deprecio Telegram bot."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Production-конфигурация Deprecio из переменных окружения или ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: str = Field(
        ...,
        validation_alias="DEPRECIO_BOT_TOKEN",
        description="Токен Telegram-бота",
    )
    admin_id: int | None = Field(None, validation_alias="ADMIN_ID")

    # Настройки парсинга
    avito_max_pages: int = Field(3, validation_alias="AVITO_MAX_PAGES")
    snapshot_ttl_hours: int = Field(24, validation_alias="SNAPSHOT_TTL_HOURS")
    gsmarena_timeout_sec: float = Field(10.0, validation_alias="GSMARENA_TIMEOUT")

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls()
