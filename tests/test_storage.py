import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from eventbot.storage.database import CURRENT_SCHEMA_VERSION
from eventbot.storage.database import create_database
from eventbot.storage.repositories import EVENT_TTL_DAYS, EventRepository, ResponseStatus


class StorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "eventbot.sqlite"
        self.database = create_database(self.database_path)
        await self.database.initialize()
        self.repository = EventRepository(self.database)

    async def asyncTearDown(self) -> None:
        self.temp_directory.cleanup()

    async def test_initialize_creates_schema(self) -> None:
        connection = await self.database.connect()
        try:
            event_count = await connection.execute_fetchall(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'events'"
            )
            response_count = await connection.execute_fetchall(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'event_responses'"
            )
            version_cursor = await connection.execute("PRAGMA user_version;")
            version = (await version_cursor.fetchone())[0]
        finally:
            await connection.close()

        self.assertEqual(len(event_count), 1)
        self.assertEqual(len(response_count), 1)
        self.assertEqual(version, CURRENT_SCHEMA_VERSION)

    async def test_create_event_sets_expiration_after_ttl_days(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)

        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Настольные игры вечером",
            now=now,
        )

        self.assertEqual(event.chat_id, -100)
        self.assertEqual(event.created_by_user_id, 42)
        self.assertEqual(event.description, "Настольные игры вечером")
        self.assertEqual(
            event.expires_at,
            (now + timedelta(days=EVENT_TTL_DAYS)).isoformat(),
        )

    async def test_set_event_message_id(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Кино",
        )

        await self.repository.set_event_message_id(event.id, 777)

        updated_event = await self.repository.get_event(event.id)
        self.assertIsNotNone(updated_event)
        self.assertEqual(updated_event.message_id, 777)

    async def test_close_event_marks_event_as_closed(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Кино",
        )

        closed_event = await self.repository.close_event(event.id)

        self.assertIsNotNone(closed_event)
        self.assertTrue(closed_event.is_closed)

    async def test_add_participant_prevents_duplicates(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Футбол",
        )

        first_insert = await self.repository.add_participant(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )
        second_insert = await self.repository.add_participant(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )

        participants = await self.repository.list_participants(event.id)

        self.assertTrue(first_insert)
        self.assertFalse(second_insert)
        self.assertEqual(len(participants), 1)
        self.assertEqual(participants[0].user_id, 1001)
        self.assertEqual(participants[0].display_name, "Максим")

        response = await self.repository.get_event_response(
            event_id=event.id,
            user_id=1001,
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.status, ResponseStatus.GOING)
        self.assertEqual(response.guests_count, 0)

    async def test_set_response_status_upserts_user_choice(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Футбол",
        )

        response = await self.repository.set_response_status(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
            status=ResponseStatus.MAYBE,
        )

        self.assertEqual(response.status, ResponseStatus.MAYBE)
        self.assertEqual(response.guests_count, 0)

        updated_response = await self.repository.set_response_status(
            event_id=event.id,
            user_id=1001,
            display_name="Максим Новое Имя",
            status=ResponseStatus.NOT_GOING,
        )
        responses = await self.repository.list_event_responses(event.id)

        self.assertEqual(updated_response.id, response.id)
        self.assertEqual(updated_response.display_name, "Максим Новое Имя")
        self.assertEqual(updated_response.status, ResponseStatus.NOT_GOING)
        self.assertEqual(len(responses), 1)

    async def test_increment_guests_creates_going_response(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Футбол",
        )

        first_response = await self.repository.increment_guests(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )
        second_response = await self.repository.increment_guests(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )

        self.assertEqual(first_response.status, ResponseStatus.GOING)
        self.assertEqual(first_response.guests_count, 1)
        self.assertEqual(second_response.guests_count, 2)

    async def test_decrement_guests_does_not_go_below_zero(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Футбол",
        )
        await self.repository.increment_guests(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )

        first_response = await self.repository.decrement_guests(
            event_id=event.id,
            user_id=1001,
        )
        second_response = await self.repository.decrement_guests(
            event_id=event.id,
            user_id=1001,
        )

        self.assertIsNotNone(first_response)
        self.assertIsNotNone(second_response)
        self.assertEqual(first_response.guests_count, 0)
        self.assertEqual(second_response.guests_count, 0)

    async def test_clear_guests_resets_guest_count(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Футбол",
        )
        await self.repository.increment_guests(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )
        await self.repository.increment_guests(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )

        response = await self.repository.clear_guests(
            event_id=event.id,
            user_id=1001,
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.guests_count, 0)

    async def test_non_going_status_resets_guest_count(self) -> None:
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Футбол",
        )
        await self.repository.increment_guests(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
        )

        response = await self.repository.set_response_status(
            event_id=event.id,
            user_id=1001,
            display_name="Максим",
            status=ResponseStatus.NOT_GOING,
        )

        self.assertEqual(response.status, ResponseStatus.NOT_GOING)
        self.assertEqual(response.guests_count, 0)

    async def test_initialize_migrates_v1_participants_to_v2_responses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.sqlite"
            connection = await aiosqlite.connect(database_path)
            try:
                await connection.executescript(
                    """
                    PRAGMA foreign_keys = ON;

                    CREATE TABLE events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER NOT NULL,
                        message_id INTEGER,
                        created_by_user_id INTEGER NOT NULL,
                        description TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        is_closed INTEGER NOT NULL DEFAULT 0
                    );

                    CREATE TABLE participants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        display_name TEXT NOT NULL,
                        joined_at TEXT NOT NULL,
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
                        UNIQUE(event_id, user_id)
                    );

                    INSERT INTO events (
                        id,
                        chat_id,
                        message_id,
                        created_by_user_id,
                        description,
                        created_at,
                        expires_at
                    )
                    VALUES (
                        1,
                        -100,
                        55,
                        42,
                        'Старое событие',
                        '2026-08-25T12:00:00+00:00',
                        '2026-09-22T12:00:00+00:00'
                    );

                    INSERT INTO participants (
                        event_id,
                        user_id,
                        display_name,
                        joined_at
                    )
                    VALUES (
                        1,
                        1001,
                        'Анна',
                        '2026-08-25T12:05:00+00:00'
                    );

                    PRAGMA user_version = 1;
                    """
                )
                await connection.commit()
            finally:
                await connection.close()

            database = create_database(database_path)
            await database.initialize()
            repository = EventRepository(database)
            responses = await repository.list_event_responses(1)

            migrated_connection = await database.connect()
            try:
                version_cursor = await migrated_connection.execute("PRAGMA user_version;")
                version = (await version_cursor.fetchone())[0]
                legacy_table = await migrated_connection.execute_fetchall(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'participants'"
                )
            finally:
                await migrated_connection.close()

        self.assertEqual(version, CURRENT_SCHEMA_VERSION)
        self.assertEqual(legacy_table, [])
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].status, ResponseStatus.GOING)
        self.assertEqual(responses[0].guests_count, 0)
        self.assertEqual(responses[0].display_name, "Анна")

    async def test_delete_expired_events_cascades_participants(self) -> None:
        old_now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
        event = await self.repository.create_event(
            chat_id=-100,
            created_by_user_id=42,
            description="Старое событие",
            now=old_now,
        )
        await self.repository.add_participant(
            event_id=event.id,
            user_id=1001,
            display_name="Анна",
            now=old_now,
        )

        deleted_count = await self.repository.delete_expired_events(
            now=old_now + timedelta(days=EVENT_TTL_DAYS + 1)
        )
        participants = await self.repository.list_participants(event.id)

        self.assertEqual(deleted_count, 1)
        self.assertIsNone(await self.repository.get_event(event.id))
        self.assertEqual(participants, [])
