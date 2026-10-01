"""Telegram Bot Entrypoint for Deprecio."""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from deprecio.bot.config import BotConfig
from deprecio.bot.handlers import base_router, compare_router, device_router, inline_router, new_releases_router
from deprecio.bot.dependencies import build_dependencies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("deprecio_bot")


async def run_bot() -> None:
    """Запуск long-polling цикла Telegram-бота."""
    config = BotConfig.from_env()
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())
    catalog, market_aggregator = build_dependencies()
    dp["catalog"] = catalog
    dp["market_aggregator"] = market_aggregator

    @dp.error()
    async def handle_bot_error(event: ErrorEvent) -> bool:
        if event.update.message:
            await event.update.message.answer(
                "Не удалось получить данные сейчас. Попробуйте повторить запрос немного позже."
            )
        return True

    # Регистрация роутеров
    dp.include_router(base_router)
    dp.include_router(compare_router)
    dp.include_router(device_router)
    dp.include_router(new_releases_router)
    dp.include_router(inline_router)

    logger.info("Бот Deprecio успешно запущен и ожидает сообщений...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_bot())
