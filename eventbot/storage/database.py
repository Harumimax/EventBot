from __future__ import annotations

from pathlib import Path

import aiosqlite


CURRENT_SCHEMA_VERSION = 3

SCHEMA_V3 = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    message_id INTEGER,
    created_by_user_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    is_closed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_chat_id ON events(chat_id);
CREATE INDEX IF NOT EXISTS idx_events_expires_at ON events(expires_at);

CREATE TABLE IF NOT EXISTS event_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('no_answer', 'going', 'not_going', 'maybe')),
    guests_count INTEGER NOT NULL DEFAULT 0 CHECK (guests_count >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    UNIQUE(event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_event_responses_event_id
    ON event_responses(event_id);
CREATE INDEX IF NOT EXISTS idx_event_responses_event_status
    ON event_responses(event_id, status);
"""

MIGRATE_V1_TO_V2 = """
CREATE TABLE IF NOT EXISTS event_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('going', 'not_going', 'maybe')),
    guests_count INTEGER NOT NULL DEFAULT 0 CHECK (guests_count >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    UNIQUE(event_id, user_id)
);

INSERT OR IGNORE INTO event_responses (
    event_id,
    user_id,
    display_name,
    status,
    guests_count,
    created_at,
    updated_at
)
SELECT
    event_id,
    user_id,
    display_name,
    'going',
    0,
    joined_at,
    joined_at
FROM participants;

CREATE INDEX IF NOT EXISTS idx_event_responses_event_id
    ON event_responses(event_id);
CREATE INDEX IF NOT EXISTS idx_event_responses_event_status
    ON event_responses(event_id, status);

DROP TABLE participants;
PRAGMA user_version = 2;
"""

MIGRATE_V2_TO_V3 = """
CREATE TABLE event_responses_v3 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('no_answer', 'going', 'not_going', 'maybe')),
    guests_count INTEGER NOT NULL DEFAULT 0 CHECK (guests_count >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    UNIQUE(event_id, user_id)
);

INSERT INTO event_responses_v3 (
    id,
    event_id,
    user_id,
    display_name,
    status,
    guests_count,
    created_at,
    updated_at
)
SELECT
    id,
    event_id,
    user_id,
    display_name,
    status,
    guests_count,
    created_at,
    updated_at
FROM event_responses;

DROP TABLE event_responses;
ALTER TABLE event_responses_v3 RENAME TO event_responses;

CREATE INDEX IF NOT EXISTS idx_event_responses_event_id
    ON event_responses(event_id);
CREATE INDEX IF NOT EXISTS idx_event_responses_event_status
    ON event_responses(event_id, status);

PRAGMA user_version = 3;
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def connect(self) -> aiosqlite.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    async def initialize(self) -> None:
        connection = await self.connect()
        try:
            version = await _get_user_version(connection)

            if version == 0:
                await connection.executescript(SCHEMA_V3)
                await _set_user_version(connection, CURRENT_SCHEMA_VERSION)
            elif version == 1:
                await connection.executescript(MIGRATE_V1_TO_V2)
                await connection.executescript(MIGRATE_V2_TO_V3)
            elif version == 2:
                await connection.executescript(MIGRATE_V2_TO_V3)
            elif version == CURRENT_SCHEMA_VERSION:
                await connection.executescript(SCHEMA_V3)
            else:
                raise RuntimeError(f"Unsupported database schema version: {version}")

            await connection.commit()
        finally:
            await connection.close()


async def _get_user_version(connection: aiosqlite.Connection) -> int:
    cursor = await connection.execute("PRAGMA user_version;")
    row = await cursor.fetchone()
    return int(row[0])


async def _set_user_version(connection: aiosqlite.Connection, version: int) -> None:
    await connection.execute(f"PRAGMA user_version = {version};")


def create_database(path: str | Path) -> Database:
    return Database(Path(path))
