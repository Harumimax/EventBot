from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from eventbot.config import load_settings
from eventbot.handlers import common_router
from eventbot.storage.database import create_database


async def run_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()
    database = create_database(settings.database_path)
    await database.initialize()

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(common_router)

    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())
