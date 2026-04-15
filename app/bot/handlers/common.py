from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.dependencies import build_server_repository, session_provider

router = Router()


@router.message(CommandStart())
@router.message(lambda m: m.text == "🚀 Начать / Главное меню")
async def start_handler(message: Message) -> None:
    await message.answer(
        "Добро пожаловать в VPN-бот. Выберите действие в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(lambda m: m.text == "ℹ️ Помощь")
async def help_handler(message: Message) -> None:
    await message.answer(
        "Доступные действия: пробный период, покупка подписки, поддержка, мои обращения. "
        "Для админов: /tickets, /ticket_reply, /ticket_close"
    )


@router.message(lambda m: m.text == "🌍 Выбрать сервер")
async def list_servers_handler(message: Message) -> None:
    async for session in session_provider():
        servers = await build_server_repository(session).list_active()
        if not servers:
            await message.answer("Сейчас нет доступных серверов.")
            return
        lines = [f"{s.id}. {s.name}" for s in servers]
        await message.answer("Доступные серверы:\n" + "\n".join(lines))
        break
