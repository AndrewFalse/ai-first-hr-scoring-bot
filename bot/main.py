"""
Точка входа Telegram-бота.
Инициализация бота, диспетчера и подключение роутеров.
"""

import asyncio
import logging
import sys

import asyncpg
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers.candidate import router as candidate_router
from bot.handlers.admin import router as admin_router
from bot.config import settings
from bot.db.pool import create_pool


async def on_startup(dispatcher: Dispatcher, bot: Bot) -> None:
    pool: asyncpg.Pool = await create_pool()
    dispatcher["db_pool"] = pool
    logging.info("Database pool created")


async def on_shutdown(dispatcher: Dispatcher, bot: Bot) -> None:
    pool: asyncpg.Pool = dispatcher.get("db_pool")
    if pool:
        await pool.close()
        logging.info("Database pool closed")


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.include_router(admin_router)
    dp.include_router(candidate_router)

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
