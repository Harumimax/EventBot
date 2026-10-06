import unittest

from eventbot.services.rendering import (
    EventAction,
    build_event_callback_data,
    build_event_keyboard,
    build_event_message_stats,
    build_join_callback_data,
    format_event_message,
    format_expired_event_message,
    format_response_time,
    format_user_link,
    parse_event_callback_data,
    parse_join_callback_data,
)
from eventbot.storage.repositories import Event, EventGuest, EventResponse, ResponseStatus


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

    def test_parse_join_callback_data_accepts_legacy_join_action(self) -> None:
        parsed = parse_event_callback_data("event:join:123")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.action, EventAction.GOING)
        self.assertEqual(parsed.event_id, 123)
        self.assertEqual(parse_join_callback_data("event:join:123"), 123)

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

    def test_format_event_message_marks_closed_event(self) -> None:
        event = _event(description="Футбол в субботу", is_closed=True)

        message = format_event_message(event, [])

        self.assertIn("🔒 Event closed", message)

    def test_format_event_message_escapes_html_text(self) -> None:
        event = _event(description="Rock & Roll <test>")
        responses = [
            _response(
                user_id=10,
                display_name="A&B <Max>",
                status=ResponseStatus.GOING,
                guests_count=0,
            )
        ]

        message = format_event_message(event, responses)

        self.assertIn("👉 Rock &amp; Roll &lt;test&gt; 👈", message)
        self.assertIn(
            '✅ <a href="tg://user?id=10">A&amp;B &lt;Max&gt;</a> - 25 августа 15:00',
            message,
        )

    def test_format_expired_event_message_appends_closed_text(self) -> None:
        event = _event(description="Футбол в субботу")

        message = format_expired_event_message(event, [])

        self.assertNotIn("🔒 Event closed", message)
        self.assertTrue(message.endswith("\n\nсобытие закрыто"))

    def test_format_event_message_with_grouped_responses_and_guests(self) -> None:
        event = _event(description="Потренить в понедельник в 20:00")
        responses = [
            _response(
                user_id=10,
                display_name="Арена Альфа",
                status=ResponseStatus.GOING,
                guests_count=0,
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
            _response(
                user_id=50,
                display_name="Олег",
                status=ResponseStatus.NO_ANSWER,
                guests_count=0,
            ),
        ]

        guests = [
            _guest(1, 10, "Арена Альфа", created_at="2026-08-25T12:00:00+00:00"),
            _guest(2, 30, "Alb", created_at="2026-08-25T12:10:00+00:00"),
            _guest(3, 30, "Alb", created_at="2026-08-25T12:20:00+00:00"),
            _guest(4, 40, "Максим", created_at="2026-08-25T12:30:00+00:00"),
            _guest(5, 50, "Олег", created_at="2026-08-25T12:40:00+00:00"),
        ]

        message = format_event_message(event, responses, guests)

        self.assertEqual(
            message,
            "👉 Потренить в понедельник в 20:00 👈\n"
            "\n"
            "Going😀:\n"
            '✅ <a href="tg://user?id=10">Арена Альфа</a> - 25 августа 15:00\n'
            '✅ <a href="tg://user?id=20">Aleksandr Tenkalyuk</a> - 25 августа 15:00\n'
            '➕1, from: <a href="tg://user?id=10">Арена Альфа</a> - 25 августа 15:00\n'
            '➕1, from: <a href="tg://user?id=30">Alb</a> - 25 августа 15:10\n'
            '➕2, from: <a href="tg://user?id=30">Alb</a> - 25 августа 15:20\n'
            '➕1, from: <a href="tg://user?id=40">Максим</a> - 25 августа 15:30\n'
            '➕1, from: <a href="tg://user?id=50">Олег</a> - 25 августа 15:40\n'
            "\n"
            "Not going😐:\n"
            '❌ <a href="tg://user?id=30">Alb</a> - 25 августа 15:00\n'
            "\n"
            "Not sure🤔:\n"
            '💭 <a href="tg://user?id=40">Максим</a> - 25 августа 15:00\n'
            "\n"
            "Total going: 7\n"
            "✅: 2\n"
            "➕: 5\n"
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
                guests_count=0,
            )
        ]
        guests = [
            _guest(1, 10, "Анна", created_at="2026-08-25T12:00:00+00:00"),
            _guest(2, 10, "Анна", created_at="2026-08-25T12:10:00+00:00"),
            _guest(3, 10, "Анна", created_at="2026-08-25T12:20:00+00:00"),
        ]

        message = format_event_message(event, responses, guests)

        self.assertIn('➕1, from: <a href="tg://user?id=10">Анна</a> - 25 августа 15:00', message)
        self.assertIn('➕2, from: <a href="tg://user?id=10">Анна</a> - 25 августа 15:10', message)
        self.assertIn('➕3, from: <a href="tg://user?id=10">Анна</a> - 25 августа 15:20', message)
        self.assertIn("Total going: 4", message)

    def test_format_user_link_uses_telegram_user_id(self) -> None:
        response = _response(
            user_id=12345,
            display_name="Максим",
            status=ResponseStatus.GOING,
            guests_count=0,
        )

        self.assertEqual(
            format_user_link(response),
            '<a href="tg://user?id=12345">Максим</a>',
        )

    def test_format_user_link_hides_username_suffix(self) -> None:
        response = _response(
            user_id=12345,
            display_name="Латухин Максим (@harumimax)",
            status=ResponseStatus.GOING,
            guests_count=0,
        )

        self.assertEqual(
            format_user_link(response),
            '<a href="tg://user?id=12345">Латухин Максим</a>',
        )

    def test_format_response_time_uses_moscow_timezone_and_russian_month(self) -> None:
        self.assertEqual(
            format_response_time("2026-10-10T09:10:00+00:00"),
            "10 октября 12:10",
        )

    def test_build_event_message_stats_counts_all_guests(self) -> None:
        responses = [
            _response(10, "Going", ResponseStatus.GOING, guests_count=2),
            _response(20, "No", ResponseStatus.NOT_GOING, guests_count=5),
            _response(30, "Maybe", ResponseStatus.MAYBE, guests_count=4),
            _response(40, "No answer", ResponseStatus.NO_ANSWER, guests_count=3),
        ]

        guests = [
            _guest(1, 10, "Going"),
            _guest(2, 10, "Going"),
            _guest(3, 20, "No"),
            _guest(4, 30, "Maybe"),
            _guest(5, 40, "No answer"),
        ]

        stats = build_event_message_stats(responses, guests)

        self.assertEqual(stats.going_count, 1)
        self.assertEqual(stats.guests_count, 5)
        self.assertEqual(stats.total_going, 6)
        self.assertEqual(stats.not_going_count, 1)
        self.assertEqual(stats.maybe_count, 1)


def _event(description: str, is_closed: bool = False) -> Event:
    return Event(
        id=1,
        chat_id=-100,
        message_id=55,
        created_by_user_id=42,
        description=description,
        created_at="2026-08-25T12:00:00+00:00",
        expires_at="2026-09-22T12:00:00+00:00",
        is_closed=is_closed,
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


def _guest(
    id: int,
    user_id: int,
    display_name: str,
    created_at: str = "2026-08-25T12:00:00+00:00",
) -> EventGuest:
    return EventGuest(
        id=id,
        event_id=1,
        user_id=user_id,
        display_name=display_name,
        created_at=created_at,
    )
