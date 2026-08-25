from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from eventbot.storage.repositories import EventRepository


logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
SleepCallable = Callable[[float], Awaitable[None]]


async def run_cleanup_once(
    event_repository: EventRepository,
    *,
    now: datetime | None = None,
) -> int:
    deleted_count = await event_repository.delete_expired_events(
        now=now or datetime.now(UTC)
    )

    if deleted_count:
        logger.info("Deleted %s expired events", deleted_count)

    return deleted_count


async def run_cleanup_loop(
    event_repository: EventRepository,
    *,
    interval_seconds: float = CLEANUP_INTERVAL_SECONDS,
    sleep: SleepCallable = asyncio.sleep,
) -> None:
    while True:
        await run_cleanup_once(event_repository)
        await sleep(interval_seconds)
