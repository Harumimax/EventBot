import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eventbot.config import DEFAULT_DATABASE_PATH, load_dotenv, load_settings


class ConfigTests(unittest.TestCase):
    def test_load_settings_reads_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "DATABASE_PATH": "./custom.sqlite",
            },
            clear=True,
        ):
            settings = load_settings(dotenv_path=Path("missing.env"))

        self.assertEqual(settings.telegram_bot_token, "token")
        self.assertEqual(settings.database_path, Path("./custom.sqlite"))

    def test_load_settings_uses_default_database_path(self) -> None:
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token"}, clear=True):
            settings = load_settings(dotenv_path=Path("missing.env"))

        self.assertEqual(settings.database_path, Path(DEFAULT_DATABASE_PATH))

    def test_load_settings_requires_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "TELEGRAM_BOT_TOKEN"):
                load_settings(dotenv_path=Path("missing.env"))

    def test_load_dotenv_preserves_existing_environment_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "TELEGRAM_BOT_TOKEN=from_file\nDATABASE_PATH=./data.sqlite\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"TELEGRAM_BOT_TOKEN": "from_environment"},
                clear=True,
            ):
                load_dotenv(env_path)

                self.assertEqual(os.environ["TELEGRAM_BOT_TOKEN"], "from_environment")
                self.assertEqual(os.environ["DATABASE_PATH"], "./data.sqlite")
