import asyncio
import unittest
from dataclasses import replace
from datetime import UTC, datetime

from aiogram.enums import ParseMode

from eventbot.services.cleanup import run_cleanup_loop, run_cleanup_once
from eventbot.storage.repositories import Event, EventGuest, EventResponse, ResponseStatus


class FakeEventRepository:
    def __init__(
        self,
        *,
        expired_events: list[Event] | None = None,
        responses: list[EventResponse] | None = None,
        guests: list[EventGuest] | None = None,
    ) -> None:
        self.expired_events = expired_events or []
        self.responses = responses or []
        self.guests = guests or []
        self.list_expired_calls: list[datetime] = []
        self.response_event_ids: list[int] = []
        self.guest_event_ids: list[int] = []
        self.deleted_event_ids: list[int] = []

    async def list_expired_events(self, now: datetime | None = None) -> list[Event]:
        if now is None:
            raise AssertionError("cleanup should pass an explicit timestamp")

        self.list_expired_calls.append(now)
        return self.expired_events

    async def list_event_responses(self, event_id: int) -> list[EventResponse]:
        self.response_event_ids.append(event_id)
        return [response for response in self.responses if response.event_id == event_id]

    async def list_event_guests(self, event_id: int) -> list[EventGuest]:
        self.guest_event_ids.append(event_id)
        return [guest for guest in self.guests if guest.event_id == event_id]

    async def delete_event(self, event_id: int) -> bool:
        self.deleted_event_ids.append(event_id)
        return True


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []

    async def edit_message_text(
        self,
        text: str,
        *,
        chat_id: int,
        message_id: int,
        reply_markup: object | None = None,
        parse_mode: str | None = None,
    ) -> object:
        self.edits.append(
            {
                "text": text,
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
            }
        )
        return object()


class CleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_cleanup_once_finalizes_message_before_delete(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
        event = _event(id=1, chat_id=-100, message_id=55)
        repository = FakeEventRepository(
            expired_events=[event],
            responses=[
                _response(
                    event_id=1,
                    user_id=1001,
                    display_name="Максим",
                    status=ResponseStatus.GOING,
                    guests_count=1,
                )
            ],
        )
        bot = FakeBot()

        deleted_count = await run_cleanup_once(
            repository,  # type: ignore[arg-type]
            bot=bot,
            now=now,
        )

        self.assertEqual(deleted_count, 1)
        self.assertEqual(repository.list_expired_calls, [now])
        self.assertEqual(repository.response_event_ids, [1])
        self.assertEqual(repository.guest_event_ids, [1])
        self.assertEqual(repository.deleted_event_ids, [1])
        self.assertEqual(len(bot.edits), 1)
        self.assertEqual(bot.edits[0]["chat_id"], -100)
        self.assertEqual(bot.edits[0]["message_id"], 55)
        self.assertIsNone(bot.edits[0]["reply_markup"])
        self.assertEqual(bot.edits[0]["parse_mode"], ParseMode.HTML)
        self.assertTrue(str(bot.edits[0]["text"]).endswith("\n\nсобытие закрыто"))

    async def test_run_cleanup_once_skips_message_edit_without_message_id(self) -> None:
        repository = FakeEventRepository(
            expired_events=[replace(_event(id=1), message_id=None)],
        )
        bot = FakeBot()

        deleted_count = await run_cleanup_once(
            repository,  # type: ignore[arg-type]
            bot=bot,
        )

        self.assertEqual(deleted_count, 1)
        self.assertEqual(bot.edits, [])
        self.assertEqual(repository.deleted_event_ids, [1])

    async def test_run_cleanup_loop_runs_once_then_sleeps(self) -> None:
        repository = FakeEventRepository()
        sleep_calls: list[float] = []

        async def stop_after_first_sleep(interval_seconds: float) -> None:
            sleep_calls.append(interval_seconds)
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await run_cleanup_loop(
                repository,  # type: ignore[arg-type]
                interval_seconds=60,
                sleep=stop_after_first_sleep,
            )

        self.assertEqual(len(repository.list_expired_calls), 1)
        self.assertEqual(sleep_calls, [60])


def _event(
    *,
    id: int,
    chat_id: int = -100,
    message_id: int | None = 55,
) -> Event:
    return Event(
        id=id,
        chat_id=chat_id,
        message_id=message_id,
        created_by_user_id=42,
        description="Футбол",
        created_at="2026-08-25T12:00:00+00:00",
        expires_at="2026-09-22T12:00:00+00:00",
        is_closed=False,
    )


def _response(
    *,
    event_id: int,
    user_id: int,
    display_name: str,
    status: ResponseStatus,
    guests_count: int,
) -> EventResponse:
    return EventResponse(
        id=user_id,
        event_id=event_id,
        user_id=user_id,
        display_name=display_name,
        status=status,
        guests_count=guests_count,
        created_at="2026-08-25T12:00:00+00:00",
        updated_at="2026-08-25T12:00:00+00:00",
    )


def _guest(
    *,
    event_id: int,
    user_id: int,
    display_name: str,
) -> EventGuest:
    return EventGuest(
        id=user_id,
        event_id=event_id,
        user_id=user_id,
        display_name=display_name,
        created_at="2026-08-25T12:00:00+00:00",
    )
