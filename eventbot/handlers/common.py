from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message


router = Router(name="common")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Я помогаю собирать участников на события в групповых чатах.\n"
        "Добавь меня в группу и используй /newevent описание события."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/newevent описание - создать событие в группе"
    )
