from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from eventbot.storage.repositories import Event, Participant


JOIN_CALLBACK_PREFIX = "event:join:"


def build_join_callback_data(event_id: int) -> str:
    return f"{JOIN_CALLBACK_PREFIX}{event_id}"


def parse_join_callback_data(callback_data: str | None) -> int | None:
    if callback_data is None or not callback_data.startswith(JOIN_CALLBACK_PREFIX):
        return None

    raw_event_id = callback_data.removeprefix(JOIN_CALLBACK_PREFIX)
    if not raw_event_id.isdecimal():
        return None

    event_id = int(raw_event_id)
    return event_id if event_id > 0 else None


def build_event_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Участвую",
                    callback_data=build_join_callback_data(event_id),
                )
            ]
        ]
    )


def format_event_message(event: Event, participants: list[Participant]) -> str:
    lines = [
        "Событие:",
        event.description,
        "",
        f"Участники: {len(participants)}",
    ]

    if participants:
        lines.extend(
            f"{index}. {participant.display_name}"
            for index, participant in enumerate(participants, start=1)
        )
    else:
        lines.append("Пока никто не записался.")

    return "\n".join(lines)
