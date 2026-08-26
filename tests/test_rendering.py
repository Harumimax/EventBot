import unittest

from eventbot.services.rendering import (
    EventAction,
    build_event_callback_data,
    build_event_keyboard,
    build_event_message_stats,
    build_join_callback_data,
    format_event_message,
    parse_event_callback_data,
    parse_join_callback_data,
)
from eventbot.storage.repositories import Event, EventResponse, ResponseStatus


class RenderingTests(unittest.TestCase):
    def test_build_and_parse_event_callback_data(self) -> None:
        for action in EventAction:
            callback_data = build_event_callback_data(action, 123)
            parsed = parse_event_callback_data(callback_data)

            self.assertIsNotNone(parsed)
            self.assertEqual(parsed.action, action)
            self.assertEqual(parsed.event_id, 123)

    def test_build_and_parse_join_callback_data_remains_compatible(self) -> None:
        callback_data = build_join_callback_data(123)

        self.assertEqual(callback_data, "event:going:123")
        self.assertEqual(parse_join_callback_data(callback_data), 123)

    def test_parse_event_callback_data_rejects_invalid_data(self) -> None:
        self.assertIsNone(parse_event_callback_data(None))
        self.assertIsNone(parse_event_callback_data(""))
        self.assertIsNone(parse_event_callback_data("event:going"))
        self.assertIsNone(parse_event_callback_data("event:going:"))
        self.assertIsNone(parse_event_callback_data("event:going:abc"))
        self.assertIsNone(parse_event_callback_data("event:going:0"))
        self.assertIsNone(parse_event_callback_data("wrong:going:123"))
        self.assertIsNone(parse_event_callback_data("event:delete:123"))

    def test_parse_join_callback_data_rejects_non_going_actions(self) -> None:
        self.assertIsNone(parse_join_callback_data("event:not_going:123"))
        self.assertIsNone(parse_join_callback_data("event:maybe:123"))
        self.assertIsNone(parse_join_callback_data("event:plus_one:123"))

    def test_build_event_keyboard_contains_all_event_buttons(self) -> None:
        keyboard = build_event_keyboard(7)
        rows = keyboard.inline_keyboard

        self.assertEqual([button.text for button in rows[0]], ["🔒 Close event"])
        self.assertEqual(
            [button.text for button in rows[1]],
            ["✅ Going", "❌ Not going", "💭 Thinking"],
        )
        self.assertEqual(
            [button.text for button in rows[2]],
            ["➕ +1", "➖ -1", "🧹 - All"],
        )
        self.assertEqual(rows[0][0].callback_data, "event:close:7")
        self.assertEqual(rows[1][0].callback_data, "event:going:7")
        self.assertEqual(rows[1][1].callback_data, "event:not_going:7")
        self.assertEqual(rows[1][2].callback_data, "event:maybe:7")
        self.assertEqual(rows[2][0].callback_data, "event:plus_one:7")
        self.assertEqual(rows[2][1].callback_data, "event:minus_one:7")
        self.assertEqual(rows[2][2].callback_data, "event:clear_guests:7")

    def test_format_event_message_without_responses(self) -> None:
        event = _event(description="Футбол в субботу")

        message = format_event_message(event, [])

        self.assertEqual(
            message,
            "👉 Футбол в субботу 👈\n"
            "\n"
            "Going😀:\n"
            "\n"
            "Not going😐:\n"
            "\n"
            "Not sure🤔:\n"
            "\n"
            "Total going: 0\n"
            "✅: 0\n"
            "➕: 0\n"
            "❌: 0\n"
            "💭: 0",
        )

    def test_format_event_message_with_grouped_responses_and_guests(self) -> None:
        event = _event(description="Потренить в понедельник в 20:00")
        responses = [
            _response(
                user_id=10,
                display_name="Арена Альфа",
                status=ResponseStatus.GOING,
                guests_count=1,
            ),
            _response(
                user_id=20,
                display_name="Aleksandr Tenkalyuk",
                status=ResponseStatus.GOING,
                guests_count=0,
            ),
            _response(
                user_id=30,
                display_name="Alb",
                status=ResponseStatus.NOT_GOING,
                guests_count=0,
            ),
            _response(
                user_id=40,
                display_name="Максим",
                status=ResponseStatus.MAYBE,
                guests_count=0,
            ),
        ]

        message = format_event_message(event, responses)

        self.assertEqual(
            message,
            "👉 Потренить в понедельник в 20:00 👈\n"
            "\n"
            "Going😀:\n"
            "✅ Арена Альфа\n"
            "✅ Aleksandr Tenkalyuk\n"
            "➕1, from: Арена Альфа\n"
            "\n"
            "Not going😐:\n"
            "❌ Alb\n"
            "\n"
            "Not sure🤔:\n"
            "💭 Максим\n"
            "\n"
            "Total going: 3\n"
            "✅: 2\n"
            "➕: 1\n"
            "❌: 1\n"
            "💭: 1",
        )

    def test_format_event_message_renders_multiple_guests_from_one_user(self) -> None:
        event = _event(description="Кино")
        responses = [
            _response(
                user_id=10,
                display_name="Анна",
                status=ResponseStatus.GOING,
                guests_count=3,
            )
        ]

        message = format_event_message(event, responses)

        self.assertIn("➕1, from: Анна", message)
        self.assertIn("➕2, from: Анна", message)
        self.assertIn("➕3, from: Анна", message)
        self.assertIn("Total going: 4", message)

    def test_build_event_message_stats_counts_only_going_guests(self) -> None:
        responses = [
            _response(10, "Going", ResponseStatus.GOING, guests_count=2),
            _response(20, "No", ResponseStatus.NOT_GOING, guests_count=5),
            _response(30, "Maybe", ResponseStatus.MAYBE, guests_count=4),
        ]

        stats = build_event_message_stats(responses)

        self.assertEqual(stats.going_count, 1)
        self.assertEqual(stats.guests_count, 2)
        self.assertEqual(stats.total_going, 3)
        self.assertEqual(stats.not_going_count, 1)
        self.assertEqual(stats.maybe_count, 1)


def _event(description: str) -> Event:
    return Event(
        id=1,
        chat_id=-100,
        message_id=55,
        created_by_user_id=42,
        description=description,
        created_at="2026-08-25T12:00:00+00:00",
        expires_at="2026-09-22T12:00:00+00:00",
        is_closed=False,
    )


def _response(
    user_id: int,
    display_name: str,
    status: ResponseStatus,
    guests_count: int,
) -> EventResponse:
    return EventResponse(
        id=user_id,
        event_id=1,
        user_id=user_id,
        display_name=display_name,
        status=status,
        guests_count=guests_count,
        created_at="2026-08-25T12:00:00+00:00",
        updated_at="2026-08-25T12:00:00+00:00",
    )
