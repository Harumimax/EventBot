from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from eventbot.services.rendering import EventAction
from eventbot.storage.repositories import Event, EventResponse, ResponseStatus


class EventActionRepository(Protocol):
    async def close_event(self, event_id: int) -> Event | None:
        pass

    async def get_event_response(
        self,
        *,
        event_id: int,
        user_id: int,
    ) -> EventResponse | None:
        pass

    async def set_response_status(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
        status: ResponseStatus,
    ) -> EventResponse:
        pass

    async def increment_guests(
        self,
        *,
        event_id: int,
        user_id: int,
        display_name: str,
    ) -> EventResponse:
        pass

    async def decrement_guests(
        self,
        *,
        event_id: int,
        user_id: int,
    ) -> EventResponse | None:
        pass

    async def clear_guests(
        self,
        *,
        event_id: int,
        user_id: int,
    ) -> EventResponse | None:
        pass


@dataclass(frozen=True)
class EventActionResult:
    event: Event
    feedback_text: str
    should_update_message: bool
    remove_keyboard: bool = False


async def apply_event_action(
    *,
    repository: EventActionRepository,
    event: Event,
    action: EventAction,
    user_id: int,
    display_name: str,
) -> EventActionResult:
    if action == EventAction.CLOSE:
        return await _close_event(
            repository=repository,
            event=event,
            user_id=user_id,
        )

    if action == EventAction.GOING:
        return await _set_status(
            repository=repository,
            event=event,
            user_id=user_id,
            display_name=display_name,
            status=ResponseStatus.GOING,
            feedback_text="Marked as going.",
            unchanged_feedback_text="You are already going.",
        )

    if action == EventAction.NOT_GOING:
        return await _set_status(
            repository=repository,
            event=event,
            user_id=user_id,
            display_name=display_name,
            status=ResponseStatus.NOT_GOING,
            feedback_text="Marked as not going.",
            unchanged_feedback_text="You are already marked as not going.",
        )

    if action == EventAction.MAYBE:
        return await _set_status(
            repository=repository,
            event=event,
            user_id=user_id,
            display_name=display_name,
            status=ResponseStatus.MAYBE,
            feedback_text="Marked as thinking.",
            unchanged_feedback_text="You are already marked as thinking.",
        )

    if action == EventAction.PLUS_ONE:
        await repository.increment_guests(
            event_id=event.id,
            user_id=user_id,
            display_name=display_name,
        )
        return EventActionResult(
            event=event,
            feedback_text="Added +1.",
            should_update_message=True,
        )

    if action == EventAction.MINUS_ONE:
        existing = await repository.get_event_response(
            event_id=event.id,
            user_id=user_id,
        )
        if existing is None or existing.guests_count == 0:
            return EventActionResult(
                event=event,
                feedback_text="No +1 to remove.",
                should_update_message=False,
            )

        await repository.decrement_guests(event_id=event.id, user_id=user_id)
        return EventActionResult(
            event=event,
            feedback_text="Removed 1 guest.",
            should_update_message=True,
        )

    if action == EventAction.CLEAR_GUESTS:
        existing = await repository.get_event_response(
            event_id=event.id,
            user_id=user_id,
        )
        if existing is None or existing.guests_count == 0:
            return EventActionResult(
                event=event,
                feedback_text="No guests to remove.",
                should_update_message=False,
            )

        await repository.clear_guests(event_id=event.id, user_id=user_id)
        return EventActionResult(
            event=event,
            feedback_text="Removed all guests.",
            should_update_message=True,
        )

    raise ValueError(f"Unsupported event action: {action}")


async def _close_event(
    *,
    repository: EventActionRepository,
    event: Event,
    user_id: int,
) -> EventActionResult:
    if user_id != event.created_by_user_id:
        return EventActionResult(
            event=event,
            feedback_text="Only the event creator can close it.",
            should_update_message=False,
        )

    closed_event = await repository.close_event(event.id)
    if closed_event is None:
        return EventActionResult(
            event=event,
            feedback_text="Event was not found.",
            should_update_message=False,
        )

    return EventActionResult(
        event=closed_event,
        feedback_text="Event closed.",
        should_update_message=True,
        remove_keyboard=True,
    )


async def _set_status(
    *,
    repository: EventActionRepository,
    event: Event,
    user_id: int,
    display_name: str,
    status: ResponseStatus,
    feedback_text: str,
    unchanged_feedback_text: str,
) -> EventActionResult:
    existing = await repository.get_event_response(
        event_id=event.id,
        user_id=user_id,
    )
    await repository.set_response_status(
        event_id=event.id,
        user_id=user_id,
        display_name=display_name,
        status=status,
    )

    changed = (
        existing is None
        or existing.status != status
        or existing.display_name != display_name
    )

    return EventActionResult(
        event=event,
        feedback_text=feedback_text if changed else unchanged_feedback_text,
        should_update_message=changed,
    )
