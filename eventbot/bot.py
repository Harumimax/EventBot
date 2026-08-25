from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from eventbot.config import Settings, load_settings
from eventbot.handlers import common_router, events_router
from eventbot.storage.database import create_database
from eventbot.storage.repositories import EventRepository


async def run_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()
    database = create_database(settings.database_path)
    await database.initialize()

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = create_dispatcher(settings)
    dispatcher["event_repository"] = EventRepository(database)

    await dispatcher.start_polling(bot)


def create_dispatcher(settings: Settings) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher["settings"] = settings
    dispatcher.include_router(common_router)
    dispatcher.include_router(events_router)

    return dispatcher


def main() -> None:
    asyncio.run(run_bot())
