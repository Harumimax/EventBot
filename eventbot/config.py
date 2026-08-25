from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DATABASE_PATH = "./data/eventbot.sqlite"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    database_path: Path


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def load_settings(dotenv_path: Path = Path(".env")) -> Settings:
    load_dotenv(dotenv_path)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    database_path = Path(os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH))

    return Settings(
        telegram_bot_token=token,
        database_path=database_path,
    )
