"""Configuration and environment settings for Deprecio Telegram Bot."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def load_dotenv(dotenv_path: Optional[Path] = None) -> None:
    """Простой встроенный загрузчик .env файлов без внешних зависимостей."""
    path = dotenv_path or Path(".env")
    if not path.exists():
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


@dataclass
class BotConfig:
    """Параметры конфигурации Telegram-бота."""
    bot_token: str
    admin_id: Optional[int] = None

    @classmethod
    def from_env(cls) -> "BotConfig":
        load_dotenv()
        token = os.getenv("DEPRECIO_BOT_TOKEN") or os.getenv("BOT_TOKEN")
        if not token:
            raise ValueError(
                "Не найден токен Telegram-бота! Задайте его в файле .env (DEPRECIO_BOT_TOKEN='...') "
                "или в системных переменных окружения."
            )
        admin_id_str = os.getenv("ADMIN_ID")
        admin_id = int(admin_id_str) if admin_id_str and admin_id_str.isdigit() else None
        return cls(bot_token=token, admin_id=admin_id)
