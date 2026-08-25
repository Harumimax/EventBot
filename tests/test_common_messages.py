import unittest

from eventbot.handlers.common import HELP_TEXT


class CommonMessageTests(unittest.TestCase):
    def test_help_text_mentions_event_cleanup_after_twenty_eight_days(self) -> None:
        self.assertIn("/newevent описание", HELP_TEXT)
        self.assertIn("28 дней", HELP_TEXT)
