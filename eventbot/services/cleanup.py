from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from eventbot.services.rendering import format_expired_event_message
from eventbot.storage.repositories import EventRepository


logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
SleepCallable = Callable[[float], Awaitable[None]]


class EventMessageEditor(Protocol):
    async def edit_message_text(
        self,
        text: str,
        *,
        chat_id: int,
        message_id: int,
        reply_markup: InlineKeyboardMarkup | None = None,
        parse_mode: str | None = None,
    ) -> object:
        pass


async def run_cleanup_once(
    event_repository: EventRepository,
    *,
    bot: EventMessageEditor | None = None,
    now: datetime | None = None,
) -> int:
    current_time = now or datetime.now(UTC)
    expired_events = await event_repository.list_expired_events(now=current_time)

    deleted_count = 0
    for event in expired_events:
        if bot is not None and event.message_id is not None:
            responses = await event_repository.list_event_responses(event.id)
            guests = await event_repository.list_event_guests(event.id)
            await _finalize_event_message(
                bot=bot,
                chat_id=event.chat_id,
                message_id=event.message_id,
                text=format_expired_event_message(event, responses, guests),
            )

        if await event_repository.delete_event(event.id):
            deleted_count += 1

    if deleted_count:
        logger.info("Deleted %s expired events", deleted_count)

    return deleted_count


async def run_cleanup_loop(
    event_repository: EventRepository,
    *,
    bot: EventMessageEditor | None = None,
    interval_seconds: float = CLEANUP_INTERVAL_SECONDS,
    sleep: SleepCallable = asyncio.sleep,
) -> None:
    while True:
        await run_cleanup_once(event_repository, bot=bot)
        await sleep(interval_seconds)


async def _finalize_event_message(
    *,
    bot: EventMessageEditor,
    chat_id: int,
    message_id: int,
    text: str,
) -> None:
    try:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None,
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest as error:
        logger.warning(
            "Failed to finalize expired event message chat_id=%s message_id=%s: %s",
            chat_id,
            message_id,
            error,
        )
