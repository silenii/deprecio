"""Telegram Bot Entrypoint for Deprecio."""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from deprecio.bot.config import BotConfig
from deprecio.bot.handlers import base_router

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
    dp = Dispatcher()

    # Регистрация роутеров
    dp.include_router(base_router)

    logger.info("Бот Deprecio успешно запущен и ожидает сообщений...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_bot())
