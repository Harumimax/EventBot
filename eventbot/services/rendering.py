from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from eventbot.storage.repositories import Event, EventResponse, ResponseStatus


CALLBACK_PREFIX = "event"
EXPIRED_EVENT_SUFFIX = "событие закрыто"


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


def format_event_message(event: Event, responses: list[EventResponse]) -> str:
    going = _responses_by_status(responses, ResponseStatus.GOING)
    not_going = _responses_by_status(responses, ResponseStatus.NOT_GOING)
    maybe = _responses_by_status(responses, ResponseStatus.MAYBE)
    stats = build_event_message_stats(responses)

    lines = [
        f"👉 {escape(event.description)} 👈",
        "",
    ]
    if event.is_closed:
        lines.extend(["🔒 Event closed", ""])

    lines.append("Going😀:")
    lines.extend(f"✅ {format_user_link(response)}" for response in going)
    lines.extend(
        f"➕{guest_number}, from: {format_user_link(response)}"
        for response in responses
        for guest_number in range(1, response.guests_count + 1)
    )

    lines.extend(["", "Not going😐:"])
    lines.extend(f"❌ {format_user_link(response)}" for response in not_going)

    lines.extend(["", "Not sure🤔:"])
    lines.extend(f"💭 {format_user_link(response)}" for response in maybe)

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


def format_expired_event_message(event: Event, responses: list[EventResponse]) -> str:
    message = format_event_message(event, responses)
    if message.endswith(EXPIRED_EVENT_SUFFIX):
        return message

    return f"{message}\n\n{EXPIRED_EVENT_SUFFIX}"


def format_user_link(response: EventResponse) -> str:
    return f'<a href="tg://user?id={response.user_id}">{escape(response.display_name)}</a>'


def build_event_message_stats(responses: list[EventResponse]) -> EventMessageStats:
    return EventMessageStats(
        going_count=sum(1 for response in responses if response.status == ResponseStatus.GOING),
        guests_count=sum(response.guests_count for response in responses),
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
