from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import aiosqlite

from eventbot.storage.database import Database


EVENT_TTL_DAYS = 28


class ResponseStatus(StrEnum):
    GOING = "going"
    NOT_GOING = "not_going"
    MAYBE = "maybe"


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
class EventResponse:
    id: int
    event_id: int
    user_id: int
    display_name: str
    status: ResponseStatus
    guests_count: int
    created_at: str
    updated_at: str


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

    async def set_response_status(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
        status: ResponseStatus,
        now: datetime | None = None,
    ) -> EventResponse:
        current_timestamp = _format_timestamp(now or datetime.now(UTC))

        connection = await self.database.connect()
        try:
            await connection.execute(
                """
                INSERT INTO event_responses (
                    event_id,
                    user_id,
                    display_name,
                    status,
                    guests_count,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(event_id, user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    status = excluded.status,
                    guests_count = CASE
                        WHEN excluded.status = 'going'
                            THEN event_responses.guests_count
                        ELSE 0
                    END,
                    updated_at = excluded.updated_at
                """,
                (
                    event_id,
                    user_id,
                    display_name,
                    status.value,
                    current_timestamp,
                    current_timestamp,
                ),
            )
            await connection.commit()
        finally:
            await connection.close()

        response = await self.get_event_response(event_id=event_id, user_id=user_id)
        if response is None:
            raise RuntimeError("Event response was not found")

        return response

    async def get_event_response(
        self,
        *,
        event_id: int,
        user_id: int,
    ) -> EventResponse | None:
        connection = await self.database.connect()
        try:
            row = await _fetch_one(
                connection,
                """
                SELECT *
                FROM event_responses
                WHERE event_id = ? AND user_id = ?
                """,
                (event_id, user_id),
            )
        finally:
            await connection.close()

        return _event_response_from_row(row) if row else None

    async def list_event_responses(self, event_id: int) -> list[EventResponse]:
        connection = await self.database.connect()
        try:
            cursor = await connection.execute(
                """
                SELECT *
                FROM event_responses
                WHERE event_id = ?
                ORDER BY updated_at ASC, id ASC
                """,
                (event_id,),
            )
            rows = await cursor.fetchall()
        finally:
            await connection.close()

        return [_event_response_from_row(row) for row in rows]

    async def increment_guests(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
        now: datetime | None = None,
    ) -> EventResponse:
        current_timestamp = _format_timestamp(now or datetime.now(UTC))

        connection = await self.database.connect()
        try:
            await connection.execute(
                """
                INSERT INTO event_responses (
                    event_id,
                    user_id,
                    display_name,
                    status,
                    guests_count,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, 'going', 1, ?, ?)
                ON CONFLICT(event_id, user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    status = 'going',
                    guests_count = event_responses.guests_count + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    event_id,
                    user_id,
                    display_name,
                    current_timestamp,
                    current_timestamp,
                ),
            )
            await connection.commit()
        finally:
            await connection.close()

        response = await self.get_event_response(event_id=event_id, user_id=user_id)
        if response is None:
            raise RuntimeError("Event response was not found")

        return response

    async def decrement_guests(
        self,
        *,
        event_id: int,
        user_id: int,
        now: datetime | None = None,
    ) -> EventResponse | None:
        current_timestamp = _format_timestamp(now or datetime.now(UTC))

        connection = await self.database.connect()
        try:
            await connection.execute(
                """
                UPDATE event_responses
                SET
                    guests_count = MAX(guests_count - 1, 0),
                    updated_at = ?
                WHERE event_id = ? AND user_id = ?
                """,
                (current_timestamp, event_id, user_id),
            )
            await connection.commit()
        finally:
            await connection.close()

        return await self.get_event_response(event_id=event_id, user_id=user_id)

    async def clear_guests(
        self,
        *,
        event_id: int,
        user_id: int,
        now: datetime | None = None,
    ) -> EventResponse | None:
        current_timestamp = _format_timestamp(now or datetime.now(UTC))

        connection = await self.database.connect()
        try:
            await connection.execute(
                """
                UPDATE event_responses
                SET
                    guests_count = 0,
                    updated_at = ?
                WHERE event_id = ? AND user_id = ?
                """,
                (current_timestamp, event_id, user_id),
            )
            await connection.commit()
        finally:
            await connection.close()

        return await self.get_event_response(event_id=event_id, user_id=user_id)

    async def add_participant(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
        now: datetime | None = None,
    ) -> bool:
        existing = await self.get_event_response(event_id=event_id, user_id=user_id)
        await self.set_response_status(
            event_id=event_id,
            user_id=user_id,
            display_name=display_name,
            status=ResponseStatus.GOING,
            now=now,
        )

        return existing is None or existing.status != ResponseStatus.GOING

    async def list_participants(self, event_id: int) -> list[Participant]:
        connection = await self.database.connect()
        try:
            cursor = await connection.execute(
                """
                SELECT *
                FROM event_responses
                WHERE event_id = ? AND status = ?
                ORDER BY updated_at ASC, id ASC
                """,
                (event_id, ResponseStatus.GOING.value),
            )
            rows = await cursor.fetchall()
        finally:
            await connection.close()

        return [_participant_from_response_row(row) for row in rows]

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


def _event_response_from_row(row: aiosqlite.Row) -> EventResponse:
    return EventResponse(
        id=row["id"],
        event_id=row["event_id"],
        user_id=row["user_id"],
        display_name=row["display_name"],
        status=ResponseStatus(row["status"]),
        guests_count=row["guests_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _participant_from_response_row(row: aiosqlite.Row) -> Participant:
    return Participant(
        id=row["id"],
        event_id=row["event_id"],
        user_id=row["user_id"],
        display_name=row["display_name"],
        joined_at=row["updated_at"],
    )
