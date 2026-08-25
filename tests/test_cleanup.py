import asyncio
import unittest
from datetime import UTC, datetime

from eventbot.services.cleanup import run_cleanup_loop, run_cleanup_once


class FakeEventRepository:
    def __init__(self, deleted_count: int = 0) -> None:
        self.deleted_count = deleted_count
        self.calls: list[datetime] = []

    async def delete_expired_events(self, now: datetime | None = None) -> int:
        if now is None:
            raise AssertionError("cleanup should pass an explicit timestamp")

        self.calls.append(now)
        return self.deleted_count


class CleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_cleanup_once_deletes_expired_events(self) -> None:
        now = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
        repository = FakeEventRepository(deleted_count=3)

        deleted_count = await run_cleanup_once(repository, now=now)  # type: ignore[arg-type]

        self.assertEqual(deleted_count, 3)
        self.assertEqual(repository.calls, [now])

    async def test_run_cleanup_loop_runs_once_then_sleeps(self) -> None:
        repository = FakeEventRepository()
        sleep_calls: list[float] = []

        async def stop_after_first_sleep(interval_seconds: float) -> None:
            sleep_calls.append(interval_seconds)
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await run_cleanup_loop(
                repository,  # type: ignore[arg-type]
                interval_seconds=60,
                sleep=stop_after_first_sleep,
            )

        self.assertEqual(len(repository.calls), 1)
        self.assertEqual(sleep_calls, [60])
