from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from eventbot.services.participation import (
    join_feedback_text,
    should_update_event_message_after_join,
)
from eventbot.services.rendering import (
    build_event_keyboard,
    format_event_message,
    parse_join_callback_data,
)
from eventbot.storage.repositories import EventRepository


router = Router(name="events")


@router.message(Command("newevent"))
async def new_event(
    message: Message,
    command: CommandObject,
    event_repository: EventRepository,
) -> None:
    if message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        await message.answer(
            "Создавать события можно только в групповых чатах. "
            "Добавь меня в группу и напиши /newevent описание события."
        )
        return

    if message.from_user is None:
        await message.answer("Не получилось определить автора события.")
        return

    description = (command.args or "").strip()
    if not description:
        await message.answer("Напиши описание: /newevent настольные игры в субботу")
        return

    event = await event_repository.create_event(
        chat_id=message.chat.id,
        created_by_user_id=message.from_user.id,
        description=description,
    )
    participants = await event_repository.list_participants(event.id)
    sent_message = await message.answer(
        format_event_message(event, participants),
        reply_markup=build_event_keyboard(event.id),
    )
    await event_repository.set_event_message_id(event.id, sent_message.message_id)


@router.callback_query(F.data.startswith("event:join:"))
async def join_event(
    callback: CallbackQuery,
    event_repository: EventRepository,
) -> None:
    event_id = parse_join_callback_data(callback.data)
    if event_id is None:
        await callback.answer("Не получилось прочитать кнопку события.", show_alert=True)
        return

    event = await event_repository.get_event(event_id)
    if event is None:
        await callback.answer("Событие уже не найдено.", show_alert=True)
        return

    if not isinstance(callback.message, Message):
        await callback.answer("Не получилось проверить сообщение события.", show_alert=True)
        return

    if callback.message.chat.id != event.chat_id:
        await callback.answer("Кнопка не относится к этому чату.", show_alert=True)
        return

    if event.message_id is not None and callback.message.message_id != event.message_id:
        await callback.answer("Кнопка не относится к этому сообщению.", show_alert=True)
        return

    if event.is_closed:
        await callback.answer("Запись на событие закрыта.", show_alert=True)
        return

    was_added = await event_repository.add_participant(
        event_id=event.id,
        user_id=callback.from_user.id,
        display_name=callback.from_user.full_name,
    )

    if not should_update_event_message_after_join(was_added):
        await callback.answer(join_feedback_text(was_added))
        return

    participants = await event_repository.list_participants(event.id)

    await callback.message.edit_text(
        format_event_message(event, participants),
        reply_markup=build_event_keyboard(event.id),
    )

    await callback.answer(join_feedback_text(was_added))
