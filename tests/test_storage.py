import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from eventbot.storage.database import create_database
from eventbot.storage.repositories import EVENT_TTL_DAYS, EventRepository


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
            participant_count = await connection.execute_fetchall(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'participants'"
            )
        finally:
            await connection.close()

        self.assertEqual(len(event_count), 1)
        self.assertEqual(len(participant_count), 1)

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
