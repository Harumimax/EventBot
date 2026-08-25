import unittest

from eventbot.services.participation import (
    join_feedback_text,
    should_update_event_message_after_join,
)


class ParticipationTests(unittest.TestCase):
    def test_new_participant_updates_event_message(self) -> None:
        self.assertTrue(should_update_event_message_after_join(was_added=True))
        self.assertEqual(join_feedback_text(was_added=True), "Вы записаны!")

    def test_existing_participant_does_not_update_event_message(self) -> None:
        self.assertFalse(should_update_event_message_after_join(was_added=False))
        self.assertEqual(join_feedback_text(was_added=False), "Вы уже в списке.")
