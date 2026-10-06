import unittest

from eventbot.handlers.events import (
    MAX_EVENT_DESCRIPTION_LENGTH,
    build_response_display_name,
    truncate_event_description,
)


class EventHandlerHelperTests(unittest.TestCase):
    def test_truncate_event_description_keeps_short_description(self) -> None:
        description = "Настольные игры в субботу"

        self.assertEqual(truncate_event_description(description), description)

    def test_truncate_event_description_keeps_exact_limit(self) -> None:
        description = "а" * MAX_EVENT_DESCRIPTION_LENGTH

        self.assertEqual(truncate_event_description(description), description)

    def test_truncate_event_description_adds_ellipsis_after_limit(self) -> None:
        description = "а" * (MAX_EVENT_DESCRIPTION_LENGTH + 1)

        truncated = truncate_event_description(description)

        self.assertEqual(truncated, f"{'а' * MAX_EVENT_DESCRIPTION_LENGTH}...")
        self.assertEqual(len(truncated), MAX_EVENT_DESCRIPTION_LENGTH + 3)

    def test_build_response_display_name_uses_full_name_without_username_suffix(self) -> None:
        self.assertEqual(
            build_response_display_name(full_name="Максим Иванов", username="maxim"),
            "Максим Иванов",
        )

    def test_build_response_display_name_uses_username_without_full_name(self) -> None:
        self.assertEqual(
            build_response_display_name(full_name=" ", username="maxim"),
            "@maxim",
        )

    def test_build_response_display_name_uses_full_name_without_username(self) -> None:
        self.assertEqual(
            build_response_display_name(full_name="Максим Иванов", username=None),
            "Максим Иванов",
        )
