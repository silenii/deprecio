"""Telegram Bot Entrypoint for Deprecio."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from deprecio.bot.config import BotConfig
from deprecio.bot.dependencies import build_dependencies
from deprecio.bot.handlers import (
    base_router,
    compare_router,
    device_router,
    inline_router,
    new_releases_router,
    favorites_router,
)
from deprecio.logging_config import setup_logging

logger = logging.getLogger("deprecio.bot")


async def run_bot() -> None:
    """Запуск long-polling цикла Telegram-бота."""
    setup_logging()

    try:
        config = BotConfig.from_env()
    except Exception as exc:  # noqa: BLE001
        logging.critical("startup_failed reason=invalid_config error=%s", exc)
        sys.exit(1)

    if not config.bot_token or config.bot_token.strip() == "":
        logging.critical("startup_failed reason=missing_bot_token")
        sys.exit(1)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())

    catalog, market_aggregator, favorites = build_dependencies()
    dp["catalog"] = catalog
    dp["market_aggregator"] = market_aggregator
    dp["favorites"] = favorites

    @dp.error()
    async def handle_bot_error(event: ErrorEvent) -> bool:
        logger.error(
            "unhandled_bot_error update_id=%s error=%s",
            getattr(event.update, "update_id", "?"),
            event.exception,
        )
        if event.update.message:
            await event.update.message.answer(
                "Не удалось получить данные сейчас. Попробуйте повторить запрос немного позже."
            )
        return True

    dp.include_router(base_router)
    dp.include_router(compare_router)
    dp.include_router(device_router)
    dp.include_router(new_releases_router)
    dp.include_router(favorites_router)
    dp.include_router(inline_router)

    logger.info("bot_started")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("bot_stopped")


if __name__ == "__main__":
    asyncio.run(run_bot())
