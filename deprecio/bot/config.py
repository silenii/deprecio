"""Configuration settings for the Deprecio Telegram bot."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Конфигурация Deprecio из .env / переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(
        ...,
        alias="DEPRECIO_BOT_TOKEN",
        description="Токен Telegram-бота",
    )
    admin_id: int | None = Field(None, alias="ADMIN_ID")

    # Настройки парсинга
    avito_max_pages: int = Field(3, alias="AVITO_MAX_PAGES")
    snapshot_ttl_hours: int = Field(24, alias="SNAPSHOT_TTL_HOURS")
    gsmarena_timeout_sec: float = Field(10.0, alias="GSMARENA_TIMEOUT")

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls()
