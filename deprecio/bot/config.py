"""Configuration and environment settings for Deprecio Telegram Bot."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Параметры конфигурации Telegram-бота."""
    bot_token: str
    admin_id: Optional[int] = None

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv("DEPRECIO_BOT_TOKEN") or os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError(
                "Не найден токен Telegram-бота! Задайте переменную окружения DEPRECIO_BOT_TOKEN или BOT_TOKEN."
            )
        admin_id_str = os.getenv("ADMIN_ID")
        admin_id = int(admin_id_str) if admin_id_str and admin_id_str.isdigit() else None
        return cls(bot_token=token, admin_id=admin_id)
