from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.fsm.states import SupportFlow
from app.core.config import settings
from app.dependencies import build_support_service, build_user_repository, session_provider

router = Router()


@router.message(F.text == "🛠 Поддержка")
async def support_start(message: Message, state: FSMContext) -> None:
    await message.answer("Опишите вашу проблему одним сообщением.")
    await state.set_state(SupportFlow.waiting_text)


@router.message(SupportFlow.waiting_text)
async def support_create_ticket(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return
    async for session in session_provider():
        user = await build_user_repository(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        ticket_id = await build_support_service(session).open_ticket(
            user_id=user.id,
            telegram_id=user.telegram_id,
            text=message.text[:1000],
        )
        await session.commit()
        await message.answer(f"Обращение #{ticket_id} создано. Ожидайте ответа администратора.")
        await state.clear()
        break


@router.message(Command("tickets"))
async def list_open_tickets(message: Message) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_telegram_ids:
        return
    async for session in session_provider():
        threads = await build_support_service(session).support_repo.list_open_threads()
        if not threads:
            await message.answer("Открытых тикетов нет.")
            return
        lines = [f"#{t.id} user_id={t.user_id}" for t in threads]
        await message.answer("Открытые тикеты:\n" + "\n".join(lines))
        break


@router.message(Command("ticket_reply"))
async def ticket_reply(message: Message) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_telegram_ids:
        return
    if message.text is None:
        return

    # Format: /ticket_reply <thread_id> <text>
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Формат: /ticket_reply <thread_id> <текст>")
        return

    thread_id = int(parts[1])
    reply_text = parts[2]

    async for session in session_provider():
        service = build_support_service(session)
        ok = await service.admin_reply(thread_id, message.from_user.id, reply_text[:1000])
        if not ok:
            await message.answer("Тикет не найден")
            return

        thread = await service.support_repo.get_thread(thread_id)
        if thread is None:
            return

        user_repo = build_user_repository(session)
        target_user = await user_repo.get_by_id(thread.user_id)
        await session.commit()
        await message.answer("Ответ отправлен")
        # We don't store or expose full logs; only necessary admin action metadata.
        if target_user:
            await message.bot.send_message(
                target_user.telegram_id,
                f"Ответ по тикету #{thread_id}:\n{reply_text}",
            )
        break


@router.message(Command("ticket_close"))
async def ticket_close(message: Message) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_telegram_ids:
        return
    if message.text is None:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Формат: /ticket_close <thread_id>")
        return

    thread_id = int(parts[1])
    async for session in session_provider():
        ok = await build_support_service(session).close_ticket(thread_id)
        if not ok:
            await message.answer("Тикет не найден")
            return
        await session.commit()
        await message.answer(f"Тикет #{thread_id} закрыт")
        break
