from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from aiogram.exceptions import TelegramBadRequest

from eventbot.services.event_actions import apply_event_action
from eventbot.services.rendering import (
    EventAction,
    build_event_keyboard,
    format_event_message,
    parse_event_callback_data,
)
from eventbot.storage.repositories import EventRepository


router = Router(name="events")
MAX_EVENT_DESCRIPTION_LENGTH = 200


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

    description = truncate_event_description(description)
    event = await event_repository.create_event(
        chat_id=message.chat.id,
        created_by_user_id=message.from_user.id,
        description=description,
    )
    responses = await event_repository.list_event_responses(event.id)
    sent_message = await message.answer(
        format_event_message(event, responses),
        reply_markup=build_event_keyboard(event.id),
        parse_mode=ParseMode.HTML,
    )
    await event_repository.set_event_message_id(event.id, sent_message.message_id)


@router.callback_query(F.data.startswith("event:"))
async def handle_event_action(
    callback: CallbackQuery,
    event_repository: EventRepository,
) -> None:
    parsed_callback = parse_event_callback_data(callback.data)
    if parsed_callback is None:
        await callback.answer("Не получилось прочитать кнопку события.", show_alert=True)
        return

    event = await event_repository.get_event(parsed_callback.event_id)
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

    result = await apply_event_action(
        repository=event_repository,
        event=event,
        action=parsed_callback.action,
        user_id=callback.from_user.id,
        display_name=build_response_display_name(
            full_name=callback.from_user.full_name,
            username=callback.from_user.username,
        ),
    )

    if not result.should_update_message:
        await callback.answer(result.feedback_text)
        return

    responses = await event_repository.list_event_responses(event.id)
    reply_markup = (
        None
        if result.remove_keyboard or parsed_callback.action == EventAction.CLOSE
        else build_event_keyboard(event.id)
    )

    try:
        await callback.message.edit_text(
            format_event_message(result.event, responses),
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise

    await callback.answer(result.feedback_text)


def truncate_event_description(description: str) -> str:
    if len(description) <= MAX_EVENT_DESCRIPTION_LENGTH:
        return description

    return f"{description[:MAX_EVENT_DESCRIPTION_LENGTH]}..."


def build_response_display_name(*, full_name: str, username: str | None) -> str:
    normalized_full_name = full_name.strip()
    normalized_username = (username or "").strip()

    if normalized_full_name and normalized_username:
        return f"{normalized_full_name} (@{normalized_username})"

    if normalized_username:
        return f"@{normalized_username}"

    return normalized_full_name
