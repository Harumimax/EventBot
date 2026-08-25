from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import aiosqlite

from eventbot.storage.database import Database


EVENT_TTL_DAYS = 14


@dataclass(frozen=True)
class Event:
    id: int
    chat_id: int
    message_id: int | None
    created_by_user_id: int
    description: str
    created_at: str
    expires_at: str
    is_closed: bool


@dataclass(frozen=True)
class Participant:
    id: int
    event_id: int
    user_id: int
    display_name: str
    joined_at: str


class EventRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_event(
        self,
        *,
        chat_id: int,
        created_by_user_id: int,
        description: str,
        now: datetime | None = None,
    ) -> Event:
        current_time = now or datetime.now(UTC)
        created_at = _format_timestamp(current_time)
        expires_at = _format_timestamp(current_time + timedelta(days=EVENT_TTL_DAYS))

        connection = await self.database.connect()
        try:
            cursor = await connection.execute(
                """
                INSERT INTO events (
                    chat_id,
                    created_by_user_id,
                    description,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (chat_id, created_by_user_id, description, created_at, expires_at),
            )
            await connection.commit()

            event_id = cursor.lastrowid
            if event_id is None:
                raise RuntimeError("Failed to create event")
        finally:
            await connection.close()

        event = await self.get_event(event_id)
        if event is None:
            raise RuntimeError("Created event was not found")

        return event

    async def set_event_message_id(self, event_id: int, message_id: int) -> None:
        connection = await self.database.connect()
        try:
            await connection.execute(
                "UPDATE events SET message_id = ? WHERE id = ?",
                (message_id, event_id),
            )
            await connection.commit()
        finally:
            await connection.close()

    async def get_event(self, event_id: int) -> Event | None:
        connection = await self.database.connect()
        try:
            row = await _fetch_one(
                connection,
                "SELECT * FROM events WHERE id = ?",
                (event_id,),
            )
        finally:
            await connection.close()

        return _event_from_row(row) if row else None

    async def add_participant(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
        now: datetime | None = None,
    ) -> bool:
        joined_at = _format_timestamp(now or datetime.now(UTC))

        connection = await self.database.connect()
        try:
            cursor = await connection.execute(
                """
                INSERT OR IGNORE INTO participants (
                    event_id,
                    user_id,
                    display_name,
                    joined_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (event_id, user_id, display_name, joined_at),
            )
            await connection.commit()

            return cursor.rowcount == 1
        finally:
            await connection.close()

    async def list_participants(self, event_id: int) -> list[Participant]:
        connection = await self.database.connect()
        try:
            cursor = await connection.execute(
                """
                SELECT *
                FROM participants
                WHERE event_id = ?
                ORDER BY joined_at ASC, id ASC
                """,
                (event_id,),
            )
            rows = await cursor.fetchall()
        finally:
            await connection.close()

        return [_participant_from_row(row) for row in rows]

    async def delete_expired_events(self, now: datetime | None = None) -> int:
        current_timestamp = _format_timestamp(now or datetime.now(UTC))

        connection = await self.database.connect()
        try:
            cursor = await connection.execute(
                "DELETE FROM events WHERE expires_at < ?",
                (current_timestamp,),
            )
            await connection.commit()

            return cursor.rowcount
        finally:
            await connection.close()


async def _fetch_one(
    connection: aiosqlite.Connection,
    query: str,
    params: tuple[object, ...],
) -> aiosqlite.Row | None:
    cursor = await connection.execute(query, params)
    return await cursor.fetchone()


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat()


def _event_from_row(row: aiosqlite.Row) -> Event:
    return Event(
        id=row["id"],
        chat_id=row["chat_id"],
        message_id=row["message_id"],
        created_by_user_id=row["created_by_user_id"],
        description=row["description"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        is_closed=bool(row["is_closed"]),
    )


def _participant_from_row(row: aiosqlite.Row) -> Participant:
    return Participant(
        id=row["id"],
        event_id=row["event_id"],
        user_id=row["user_id"],
        display_name=row["display_name"],
        joined_at=row["joined_at"],
    )
