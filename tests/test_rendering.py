import unittest

from eventbot.services.rendering import (
    build_event_keyboard,
    build_join_callback_data,
    format_event_message,
    parse_join_callback_data,
)
from eventbot.storage.repositories import Event, Participant


class RenderingTests(unittest.TestCase):
    def test_build_and_parse_join_callback_data(self) -> None:
        callback_data = build_join_callback_data(123)

        self.assertEqual(callback_data, "event:join:123")
        self.assertEqual(parse_join_callback_data(callback_data), 123)

    def test_parse_join_callback_data_rejects_invalid_data(self) -> None:
        self.assertIsNone(parse_join_callback_data(None))
        self.assertIsNone(parse_join_callback_data(""))
        self.assertIsNone(parse_join_callback_data("event:join:"))
        self.assertIsNone(parse_join_callback_data("event:join:abc"))
        self.assertIsNone(parse_join_callback_data("event:delete:123"))

    def test_build_event_keyboard_contains_join_button(self) -> None:
        keyboard = build_event_keyboard(7)
        button = keyboard.inline_keyboard[0][0]

        self.assertEqual(button.text, "Участвую")
        self.assertEqual(button.callback_data, "event:join:7")

    def test_format_event_message_without_participants(self) -> None:
        event = _event(description="Футбол в субботу")

        message = format_event_message(event, [])

        self.assertEqual(
            message,
            "Событие:\n"
            "Футбол в субботу\n"
            "\n"
            "Участники: 0\n"
            "Пока никто не записался.",
        )

    def test_format_event_message_with_participants(self) -> None:
        event = _event(description="Настольные игры")
        participants = [
            _participant(user_id=10, display_name="Максим"),
            _participant(user_id=20, display_name="Анна"),
        ]

        message = format_event_message(event, participants)

        self.assertEqual(
            message,
            "Событие:\n"
            "Настольные игры\n"
            "\n"
            "Участники: 2\n"
            "1. Максим\n"
            "2. Анна",
        )


def _event(description: str) -> Event:
    return Event(
        id=1,
        chat_id=-100,
        message_id=55,
        created_by_user_id=42,
        description=description,
        created_at="2026-08-25T12:00:00+00:00",
        expires_at="2026-09-08T12:00:00+00:00",
        is_closed=False,
    )


def _participant(user_id: int, display_name: str) -> Participant:
    return Participant(
        id=user_id,
        event_id=1,
        user_id=user_id,
        display_name=display_name,
        joined_at="2026-08-25T12:00:00+00:00",
    )
