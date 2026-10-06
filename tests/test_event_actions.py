import unittest

from eventbot.services.event_actions import apply_event_action
from eventbot.services.rendering import EventAction
from eventbot.storage.repositories import Event, EventGuest, EventResponse, ResponseStatus


class FakeEventActionRepository:
    def __init__(self) -> None:
        self.responses: dict[tuple[int, int], EventResponse] = {}
        self.guests: list[EventGuest] = []
        self.closed_event_ids: list[int] = []

    async def close_event(self, event_id: int) -> Event | None:
        self.closed_event_ids.append(event_id)
        return _event(id=event_id, is_closed=True)

    async def get_event_response(
        self,
        *,
        event_id: int,
        user_id: int,
    ) -> EventResponse | None:
        return self.responses.get((event_id, user_id))

    async def set_response_status(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
        status: ResponseStatus,
    ) -> EventResponse:
        existing = self.responses.get((event_id, user_id))
        guests_count = existing.guests_count if existing is not None else 0
        response = _response(
            event_id=event_id,
            user_id=user_id,
            display_name=display_name,
            status=status,
            guests_count=guests_count,
        )
        self.responses[(event_id, user_id)] = response
        return response

    async def add_guest(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
    ) -> EventGuest:
        guest = _guest(
            id=len(self.guests) + 1,
            event_id=event_id,
            user_id=user_id,
            display_name=display_name,
        )
        self.guests.append(guest)
        return guest

    async def remove_last_guest(
        self,
        *,
        event_id: int,
        user_id: int,
    ) -> EventGuest | None:
        for index in range(len(self.guests) - 1, -1, -1):
            guest = self.guests[index]
            if guest.event_id == event_id and guest.user_id == user_id:
                return self.guests.pop(index)

        return None

    async def clear_guests(
        self,
        *,
        event_id: int,
        user_id: int,
    ) -> int:
        matching_guests = [
            guest
            for guest in self.guests
            if guest.event_id == event_id and guest.user_id == user_id
        ]
        self.guests = [
            guest
            for guest in self.guests
            if guest.event_id != event_id or guest.user_id != user_id
        ]
        return len(matching_guests)


class EventActionTests(unittest.IsolatedAsyncioTestCase):
    async def test_going_sets_status_and_updates_message(self) -> None:
        repository = FakeEventActionRepository()

        result = await apply_event_action(
            repository=repository,
            event=_event(),
            action=EventAction.GOING,
            user_id=1001,
            display_name="Максим",
        )

        response = repository.responses[(1, 1001)]
        self.assertEqual(response.status, ResponseStatus.GOING)
        self.assertTrue(result.should_update_message)
        self.assertEqual(result.feedback_text, "Marked as going.")

    async def test_repeated_going_does_not_update_message(self) -> None:
        repository = FakeEventActionRepository()
        repository.responses[(1, 1001)] = _response(
            event_id=1,
            user_id=1001,
            display_name="Максим",
            status=ResponseStatus.GOING,
            guests_count=0,
        )

        result = await apply_event_action(
            repository=repository,
            event=_event(),
            action=EventAction.GOING,
            user_id=1001,
            display_name="Максим",
        )

        self.assertFalse(result.should_update_message)
        self.assertEqual(result.feedback_text, "You are already going.")

    async def test_not_going_preserves_guests_and_updates_message(self) -> None:
        repository = FakeEventActionRepository()
        repository.responses[(1, 1001)] = _response(
            event_id=1,
            user_id=1001,
            display_name="Максим",
            status=ResponseStatus.GOING,
            guests_count=0,
        )
        repository.guests = [
            _guest(id=1, event_id=1, user_id=1001, display_name="Максим"),
            _guest(id=2, event_id=1, user_id=1001, display_name="Максим"),
        ]

        result = await apply_event_action(
            repository=repository,
            event=_event(),
            action=EventAction.NOT_GOING,
            user_id=1001,
            display_name="Максим",
        )

        response = repository.responses[(1, 1001)]
        self.assertEqual(response.status, ResponseStatus.NOT_GOING)
        self.assertEqual(len(repository.guests), 2)
        self.assertTrue(result.should_update_message)

    async def test_plus_one_creates_response_without_personal_status(self) -> None:
        repository = FakeEventActionRepository()

        result = await apply_event_action(
            repository=repository,
            event=_event(),
            action=EventAction.PLUS_ONE,
            user_id=1001,
            display_name="Максим",
        )

        self.assertEqual(len(repository.guests), 1)
        self.assertEqual(repository.guests[0].display_name, "Максим")
        self.assertTrue(result.should_update_message)
        self.assertEqual(result.feedback_text, "Added +1.")

    async def test_plus_one_preserves_not_going_status(self) -> None:
        repository = FakeEventActionRepository()
        repository.responses[(1, 1001)] = _response(
            event_id=1,
            user_id=1001,
            display_name="Максим",
            status=ResponseStatus.NOT_GOING,
            guests_count=1,
        )

        result = await apply_event_action(
            repository=repository,
            event=_event(),
            action=EventAction.PLUS_ONE,
            user_id=1001,
            display_name="Максим",
        )

        response = repository.responses[(1, 1001)]
        self.assertEqual(response.status, ResponseStatus.NOT_GOING)
        self.assertEqual(len(repository.guests), 1)
        self.assertTrue(result.should_update_message)

    async def test_minus_one_without_guests_does_not_update_message(self) -> None:
        repository = FakeEventActionRepository()

        result = await apply_event_action(
            repository=repository,
            event=_event(),
            action=EventAction.MINUS_ONE,
            user_id=1001,
            display_name="Максим",
        )

        self.assertFalse(result.should_update_message)
        self.assertEqual(result.feedback_text, "No +1 to remove.")

    async def test_clear_guests_updates_message_when_guests_exist(self) -> None:
        repository = FakeEventActionRepository()
        repository.guests = [
            _guest(id=1, event_id=1, user_id=1001, display_name="Максим"),
            _guest(id=2, event_id=1, user_id=1001, display_name="Максим"),
            _guest(id=3, event_id=1, user_id=1001, display_name="Максим"),
        ]

        result = await apply_event_action(
            repository=repository,
            event=_event(),
            action=EventAction.CLEAR_GUESTS,
            user_id=1001,
            display_name="Максим",
        )

        self.assertEqual(repository.guests, [])
        self.assertTrue(result.should_update_message)
        self.assertEqual(result.feedback_text, "Removed all guests.")

    async def test_only_event_creator_can_close_event(self) -> None:
        repository = FakeEventActionRepository()

        result = await apply_event_action(
            repository=repository,
            event=_event(created_by_user_id=42),
            action=EventAction.CLOSE,
            user_id=1001,
            display_name="Максим",
        )

        self.assertFalse(result.should_update_message)
        self.assertEqual(repository.closed_event_ids, [])
        self.assertEqual(result.feedback_text, "Only the event creator can close it.")

    async def test_event_creator_can_close_event(self) -> None:
        repository = FakeEventActionRepository()

        result = await apply_event_action(
            repository=repository,
            event=_event(created_by_user_id=42),
            action=EventAction.CLOSE,
            user_id=42,
            display_name="Автор",
        )

        self.assertTrue(result.should_update_message)
        self.assertTrue(result.remove_keyboard)
        self.assertTrue(result.event.is_closed)
        self.assertEqual(repository.closed_event_ids, [1])


def _event(
    id: int = 1,
    created_by_user_id: int = 42,
    is_closed: bool = False,
) -> Event:
    return Event(
        id=id,
        chat_id=-100,
        message_id=55,
        created_by_user_id=created_by_user_id,
        description="Футбол",
        created_at="2026-08-25T12:00:00+00:00",
        expires_at="2026-09-22T12:00:00+00:00",
        is_closed=is_closed,
    )


def _response(
    *,
    event_id: int,
    user_id: int,
    display_name: str,
    status: ResponseStatus,
    guests_count: int,
) -> EventResponse:
    return EventResponse(
        id=user_id,
        event_id=event_id,
        user_id=user_id,
        display_name=display_name,
        status=status,
        guests_count=guests_count,
        created_at="2026-08-25T12:00:00+00:00",
        updated_at="2026-08-25T12:00:00+00:00",
    )


def _guest(
    *,
    id: int,
    event_id: int,
    user_id: int,
    display_name: str,
) -> EventGuest:
    return EventGuest(
        id=id,
        event_id=event_id,
        user_id=user_id,
        display_name=display_name,
        created_at="2026-08-25T12:00:00+00:00",
    )
