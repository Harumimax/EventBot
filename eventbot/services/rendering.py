from __future__ import annotations

import re

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from eventbot.storage.repositories import Event, EventGuest, EventResponse, ResponseStatus


CALLBACK_PREFIX = "event"
EXPIRED_EVENT_SUFFIX = "событие закрыто"
USERNAME_SUFFIX_PATTERN = re.compile(r"\s+\(@[^)]+\)$")
MOSCOW_TIMEZONE = timezone(timedelta(hours=3), "Europe/Moscow")
MONTH_NAMES_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


class EventAction(StrEnum):
    CLOSE = "close"
    GOING = "going"
    NOT_GOING = "not_going"
    MAYBE = "maybe"
    PLUS_ONE = "plus_one"
    MINUS_ONE = "minus_one"
    CLEAR_GUESTS = "clear_guests"


@dataclass(frozen=True)
class EventCallback:
    action: EventAction
    event_id: int


@dataclass(frozen=True)
class EventMessageStats:
    going_count: int
    guests_count: int
    not_going_count: int
    maybe_count: int

    @property
    def total_going(self) -> int:
        return self.going_count + self.guests_count


def build_event_callback_data(action: EventAction, event_id: int) -> str:
    return f"{CALLBACK_PREFIX}:{action.value}:{event_id}"


def parse_event_callback_data(callback_data: str | None) -> EventCallback | None:
    if callback_data is None:
        return None

    parts = callback_data.split(":")
    if len(parts) != 3:
        return None

    prefix, raw_action, raw_event_id = parts
    if prefix != CALLBACK_PREFIX or not raw_event_id.isdecimal():
        return None

    if raw_action == "join":
        action = EventAction.GOING
    else:
        try:
            action = EventAction(raw_action)
        except ValueError:
            return None

    event_id = int(raw_event_id)
    if event_id <= 0:
        return None

    return EventCallback(action=action, event_id=event_id)


def build_join_callback_data(event_id: int) -> str:
    return build_event_callback_data(EventAction.GOING, event_id)


def parse_join_callback_data(callback_data: str | None) -> int | None:
    parsed = parse_event_callback_data(callback_data)
    if parsed is None or parsed.action != EventAction.GOING:
        return None

    return parsed.event_id


def build_event_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔒 Close event",
                    callback_data=build_event_callback_data(EventAction.CLOSE, event_id),
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Going",
                    callback_data=build_event_callback_data(EventAction.GOING, event_id),
                ),
                InlineKeyboardButton(
                    text="❌ Not going",
                    callback_data=build_event_callback_data(
                        EventAction.NOT_GOING,
                        event_id,
                    ),
                ),
                InlineKeyboardButton(
                    text="💭 Thinking",
                    callback_data=build_event_callback_data(EventAction.MAYBE, event_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ +1",
                    callback_data=build_event_callback_data(
                        EventAction.PLUS_ONE,
                        event_id,
                    ),
                ),
                InlineKeyboardButton(
                    text="➖ -1",
                    callback_data=build_event_callback_data(
                        EventAction.MINUS_ONE,
                        event_id,
                    ),
                ),
                InlineKeyboardButton(
                    text="🧹 - All",
                    callback_data=build_event_callback_data(
                        EventAction.CLEAR_GUESTS,
                        event_id,
                    ),
                ),
            ],
        ]
    )


def format_event_message(
    event: Event,
    responses: list[EventResponse],
    guests: list[EventGuest] | None = None,
) -> str:
    event_guests = guests or []
    going = _responses_by_status(responses, ResponseStatus.GOING)
    not_going = _responses_by_status(responses, ResponseStatus.NOT_GOING)
    maybe = _responses_by_status(responses, ResponseStatus.MAYBE)
    stats = build_event_message_stats(responses, event_guests)

    lines = [
        f"👉 {escape(event.description)} 👈",
        "",
    ]
    if event.is_closed:
        lines.extend(["🔒 Event closed", ""])

    lines.append("Going😀:")
    lines.extend(f"✅ {format_response_line(response)}" for response in going)
    lines.extend(
        format_guest_line(guest, guest_number)
        for guest, guest_number in _numbered_guests(event_guests)
    )

    lines.extend(["", "Not going😐:"])
    lines.extend(f"❌ {format_response_line(response)}" for response in not_going)

    lines.extend(["", "Not sure🤔:"])
    lines.extend(f"💭 {format_response_line(response)}" for response in maybe)

    lines.extend(
        [
            "",
            f"Total going: {stats.total_going}",
            f"✅: {stats.going_count}",
            f"➕: {stats.guests_count}",
            f"❌: {stats.not_going_count}",
            f"💭: {stats.maybe_count}",
        ]
    )

    return "\n".join(lines)


def format_expired_event_message(
    event: Event,
    responses: list[EventResponse],
    guests: list[EventGuest] | None = None,
) -> str:
    message = format_event_message(event, responses, guests)
    if message.endswith(EXPIRED_EVENT_SUFFIX):
        return message

    return f"{message}\n\n{EXPIRED_EVENT_SUFFIX}"


def format_user_link(response: EventResponse | EventGuest) -> str:
    display_name = format_display_name(response.display_name)
    return f'<a href="tg://user?id={response.user_id}">{escape(display_name)}</a>'


def format_display_name(display_name: str) -> str:
    return USERNAME_SUFFIX_PATTERN.sub("", display_name).strip()


def format_response_line(response: EventResponse) -> str:
    return f"{format_user_link(response)} - {format_response_time(response.updated_at)}"


def format_guest_line(guest: EventGuest, guest_number: int) -> str:
    return (
        f"➕{guest_number}, from: "
        f"{format_user_link(guest)} - {format_response_time(guest.created_at)}"
    )


def format_response_time(timestamp: str) -> str:
    value = datetime.fromisoformat(timestamp)
    if value.tzinfo is None:
        value = value.replace(tzinfo=MOSCOW_TIMEZONE)

    local_value = value.astimezone(MOSCOW_TIMEZONE)
    month_name = MONTH_NAMES_RU[local_value.month]
    return f"{local_value.day} {month_name} {local_value:%H:%M}"


def build_event_message_stats(
    responses: list[EventResponse],
    guests: list[EventGuest] | None = None,
) -> EventMessageStats:
    event_guests = guests or []
    return EventMessageStats(
        going_count=sum(1 for response in responses if response.status == ResponseStatus.GOING),
        guests_count=len(event_guests),
        not_going_count=sum(
            1 for response in responses if response.status == ResponseStatus.NOT_GOING
        ),
        maybe_count=sum(1 for response in responses if response.status == ResponseStatus.MAYBE),
    )


def _responses_by_status(
    responses: list[EventResponse],
    status: ResponseStatus,
) -> list[EventResponse]:
    return [response for response in responses if response.status == status]


def _numbered_guests(guests: list[EventGuest]) -> list[tuple[EventGuest, int]]:
    guest_numbers_by_user: dict[int, int] = {}
    numbered_guests = []
    for guest in guests:
        guest_number = guest_numbers_by_user.get(guest.user_id, 0) + 1
        guest_numbers_by_user[guest.user_id] = guest_number
        numbered_guests.append((guest, guest_number))

    return numbered_guests
