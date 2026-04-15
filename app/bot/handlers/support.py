from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from time import monotonic

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.fsm.states import AdminSupportFlow, SupportFlow
from app.core.config import settings
from app.dependencies import build_support_service, build_user_repository, session_provider
from app.domain.enums import TicketAuthorRole

router = Router()

MENU_ACTIONS = {
    "🚀 Начать / Главное меню",
    "🎁 Пробный период",
    "🌍 Выбрать сервер",
    "💳 Купить подписку",
    "📦 Моя подписка",
    "🛠 Поддержка",
    "ℹ️ Помощь",
}

SUPPORT_MIN_INTERVAL_SECONDS = 12.0
SUPPORT_BURST_WINDOW_SECONDS = 60.0
SUPPORT_BURST_LIMIT = 5
SUPPORT_AVG_RESPONSE_MINUTES = 30

_support_last_message_at: dict[int, float] = {}
_support_user_buckets: dict[int, deque[float]] = defaultdict(deque)


def _admin_ticket_keyboard(thread_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Ответить",
                    callback_data=f"ticket_reply:{thread_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Закрыть",
                    callback_data=f"ticket_close:{thread_id}",
                ),
            ]
        ]
    )


def _format_user_ticket_line(ticket_id: int, status: str, has_messages: bool) -> str:
    suffix = "есть переписка" if has_messages else "без переписки"
    status_emoji = "🟢" if status == "OPEN" else "⚪"
    status_title = "Открыт" if status == "OPEN" else "Закрыт"
    return f"{status_emoji} #{ticket_id} • {status_title} • {suffix}"


def _pluralize_ru(value: int, one: str, few: str, many: str) -> str:
    n = abs(value) % 100
    n1 = n % 10
    if 11 <= n <= 14:
        return many
    if n1 == 1:
        return one
    if 2 <= n1 <= 4:
        return few
    return many


def _format_last_message_age(created_at: datetime | None) -> str:
    if created_at is None:
        return "нет сообщений"
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - created_at
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 1:
        return "только что"
    if total_minutes < 60:
        unit = _pluralize_ru(total_minutes, "минута", "минуты", "минут")
        return f"{total_minutes} {unit} назад"
    total_hours = total_minutes // 60
    if total_hours < 24:
        unit = _pluralize_ru(total_hours, "час", "часа", "часов")
        return f"{total_hours} {unit} назад"
    total_days = total_hours // 24
    unit = _pluralize_ru(total_days, "день", "дня", "дней")
    return f"{total_days} {unit} назад"


def _check_support_rate_limit(telegram_id: int) -> tuple[bool, int]:
    now = monotonic()
    last_at = _support_last_message_at.get(telegram_id)
    if last_at is not None:
        delta = now - last_at
        if delta < SUPPORT_MIN_INTERVAL_SECONDS:
            return False, max(1, int(SUPPORT_MIN_INTERVAL_SECONDS - delta))

    bucket = _support_user_buckets[telegram_id]
    while bucket and (now - bucket[0]) > SUPPORT_BURST_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= SUPPORT_BURST_LIMIT:
        retry_after = max(1, int(SUPPORT_BURST_WINDOW_SECONDS - (now - bucket[0])))
        return False, retry_after

    bucket.append(now)
    _support_last_message_at[telegram_id] = now
    return True, 0


@router.message(F.text == "🛠 Поддержка")
async def support_start(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Опишите проблему одним сообщением.\n"
        "Мы сохраним её в текущем обращении и уведомим поддержку."
    )
    await state.set_state(SupportFlow.waiting_text)


@router.message(SupportFlow.waiting_text, F.text.in_(MENU_ACTIONS))
async def support_cancel_by_menu_action(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Режим поддержки отменен. Выберите действие еще раз.")


@router.message(SupportFlow.waiting_text)
async def support_create_ticket(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text == "📨 Мои обращения":
        await state.clear()
        await _send_user_tickets(message)
        return
    allowed, retry_after_seconds = _check_support_rate_limit(message.from_user.id)
    if not allowed:
        await message.answer(f"Слишком часто. Попробуйте через {retry_after_seconds} сек.")
        return
    async for session in session_provider():
        user = await build_user_repository(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        ticket_id, created = await build_support_service(session).open_or_append_user_message(
            user_id=user.id,
            telegram_id=user.telegram_id,
            text=message.text[:1000],
        )
        await session.commit()
        if created:
            await message.answer(
                f"✅ Обращение #{ticket_id} принято.\n"
                "МЫ ПОДУМАЕМ НАД ВАШИМ ВОПРОСОМ!\n"
                f"⏱ Среднее время ответа: {SUPPORT_AVG_RESPONSE_MINUTES} мин."
            )
        else:
            await message.answer(
                f"✉️ Сообщение добавлено в обращение #{ticket_id}.\n"
                f"⏱ Среднее время ответа: {SUPPORT_AVG_RESPONSE_MINUTES} мин."
            )

        admin_text = (
            f"🆕 Тикет #{ticket_id}\n"
            f"Пользователь: {user.username or 'без username'} (tg_id={user.telegram_id})\n\n"
            f"{message.text[:1000]}"
        )
        for admin_id in settings.admin_telegram_ids:
            try:
                await message.bot.send_message(
                    admin_id,
                    admin_text,
                    reply_markup=_admin_ticket_keyboard(ticket_id),
                )
            except Exception:
                # Ignore single-admin delivery failures; other admins still receive alerts.
                pass
        await state.clear()
        break


@router.message(F.text == "📨 Мои обращения")
async def support_my_tickets(message: Message) -> None:
    await _send_user_tickets(message)


@router.message(SupportFlow.waiting_text, F.text == "📨 Мои обращения")
async def support_my_tickets_from_support_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _send_user_tickets(message)


async def _send_user_tickets(message: Message) -> None:
    if message.from_user is None:
        return
    async for session in session_provider():
        user = await build_user_repository(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        service = build_support_service(session)
        threads = await service.support_repo.list_threads_by_user_id(user.id, limit=5)
        if not threads:
            await message.answer(
                "У вас пока нет обращений.\n"
                "Нажмите «🛠 Поддержка», чтобы создать новый тикет."
            )
            break

        decorated_threads: list[tuple[bool, int, str]] = []
        for thread in threads:
            messages = await service.support_repo.list_messages(thread.id, limit=1)
            last_message_at = messages[-1].created_at if messages else None
            rank_open = thread.status.value == "OPEN"
            rank_ts = int(last_message_at.timestamp()) if last_message_at is not None else 0
            line = (
                f"{_format_user_ticket_line(thread.id, thread.status.value, bool(messages))}\n"
                f"   🕒 Последнее сообщение: {_format_last_message_age(last_message_at)}"
            )
            decorated_threads.append((rank_open, rank_ts, line))

        decorated_threads.sort(key=lambda item: (item[0], item[1]), reverse=True)
        lines: list[str] = ["Ваши последние обращения:"]
        for _, __, line in decorated_threads:
            lines.append(line)
        lines.append("Чтобы дописать в открытый тикет, нажмите «🛠 Поддержка».")
        await message.answer("\n".join(lines))
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


@router.callback_query(F.data.startswith("ticket_reply:"))
async def ticket_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Нет доступа", show_alert=True)
        return
    thread_id_raw = callback.data.split(":", maxsplit=1)[1]
    if not thread_id_raw.isdigit():
        await callback.answer("Некорректный тикет", show_alert=True)
        return
    thread_id = int(thread_id_raw)
    await state.set_state(AdminSupportFlow.waiting_reply)
    await state.update_data(thread_id=thread_id)
    await callback.message.answer(f"Введите ответ для тикета #{thread_id}.")
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_close:"))
async def ticket_close_from_button(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Нет доступа", show_alert=True)
        return
    thread_id_raw = callback.data.split(":", maxsplit=1)[1]
    if not thread_id_raw.isdigit():
        await callback.answer("Некорректный тикет", show_alert=True)
        return
    thread_id = int(thread_id_raw)
    async for session in session_provider():
        service = build_support_service(session)
        thread = await service.support_repo.get_thread(thread_id)
        if thread is None:
            await callback.answer("Тикет не найден", show_alert=True)
            return
        ok = await service.close_ticket(thread_id)
        if not ok:
            await callback.answer("Уже закрыт", show_alert=True)
            return
        target_user = await build_user_repository(session).get_by_id(thread.user_id)
        await session.commit()
        await callback.message.answer(f"Тикет #{thread_id} закрыт.")
        if target_user:
            await callback.message.bot.send_message(
                target_user.telegram_id,
                f"Тикет #{thread_id} закрыт администратором.",
            )
        await callback.answer("Закрыто")
        break


@router.message(AdminSupportFlow.waiting_reply)
async def ticket_reply_from_state(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_telegram_ids:
        return
    if message.text is None:
        return
    data = await state.get_data()
    thread_id = int(data.get("thread_id", 0))
    if thread_id <= 0:
        await state.clear()
        await message.answer("Контекст ответа утерян. Нажмите 'Ответить' заново.")
        return

    async for session in session_provider():
        service = build_support_service(session)
        ok = await service.admin_reply(thread_id, message.from_user.id, message.text[:1000])
        if not ok:
            await message.answer("Тикет не найден")
            await state.clear()
            return
        thread = await service.support_repo.get_thread(thread_id)
        if thread is None:
            await message.answer("Тикет не найден")
            await state.clear()
            return
        target_user = await build_user_repository(session).get_by_id(thread.user_id)
        await session.commit()
        await message.answer(f"Ответ отправлен в тикет #{thread_id}.")
        if target_user:
            await message.bot.send_message(
                target_user.telegram_id,
                f"Ответ поддержки по тикету #{thread_id}:\n{message.text[:1000]}",
            )
        await state.clear()
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


@router.message(Command("ticket"))
async def ticket_details(message: Message) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_telegram_ids:
        return
    if message.text is None:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Формат: /ticket <thread_id>")
        return
    thread_id = int(parts[1])
    async for session in session_provider():
        service = build_support_service(session)
        thread = await service.support_repo.get_thread(thread_id)
        if thread is None:
            await message.answer("Тикет не найден")
            return
        messages = await service.support_repo.list_messages(thread_id, limit=20)
        if not messages:
            await message.answer(f"Тикет #{thread_id} пуст.")
            return
        lines: list[str] = [f"Тикет #{thread_id} ({thread.status.value})"]
        for item in messages:
            role = "USER" if item.author_role == TicketAuthorRole.USER else "ADMIN"
            lines.append(f"[{role}] {item.text}")
        await message.answer("\n".join(lines))
        break
