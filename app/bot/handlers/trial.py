from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.fsm.states import TrialFlow
from app.dependencies import (
    build_billing_repository,
    build_server_repository,
    build_trial_service,
    build_user_repository,
    session_provider,
)

router = Router()


@router.message(F.text == "🎁 Пробный период")
async def start_trial(message: Message, state: FSMContext) -> None:
    async for session in session_provider():
        servers = await build_server_repository(session).list_active()
        if not servers:
            await message.answer("Нет доступных серверов. Попробуйте позже.")
            return
        lines = [f"{s.id}. {s.name}" for s in servers]
        await message.answer("Выберите сервер для триала, отправьте ID:\n" + "\n".join(lines))
        await state.set_state(TrialFlow.choosing_server)
        break


@router.message(TrialFlow.choosing_server)
async def issue_trial(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return
    if not message.text.isdigit():
        await message.answer("Введите числовой ID сервера.")
        return

    server_id = int(message.text)
    async for session in session_provider():
        user_repo = build_user_repository(session)
        server_repo = build_server_repository(session)
        trial_service = build_trial_service(session)

        user = await user_repo.get_or_create(message.from_user.id, message.from_user.username)
        server = await server_repo.get_by_id(server_id)
        if server is None:
            await message.answer("Сервер не найден.")
            return
        user_id = user.id
        server_db_id = server.id

        try:
            trial = await trial_service.issue_trial(
                user_id=user_id,
                telegram_id=user.telegram_id,
                server_id=server_db_id,
                server=server,
            )
            account = await build_billing_repository(session).get_vpn_account(user_id, server_db_id)
            await session.commit()
            link_part = f"\nСсылка для подключения:\n{account.subscription_url}" if account and account.subscription_url else ""
            await message.answer(
                "Триал активирован на 3 дня. "
                f"Окончание: {trial.ends_at:%Y-%m-%d %H:%M UTC}."
                f"{link_part}"
            )
        except ValueError as exc:
            await session.rollback()
            await message.answer(str(exc))
            account = await build_billing_repository(session).get_vpn_account(user_id, server_db_id)
            if account and account.subscription_url:
                await message.answer(f"Ваша текущая ссылка для подключения:\n{account.subscription_url}")
        except Exception:
            await session.rollback()
            await message.answer("Не удалось выдать триал. Попробуйте позже.")
        finally:
            await state.clear()
        break
