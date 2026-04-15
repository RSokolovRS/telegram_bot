from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.fsm.states import PurchaseFlow
from app.dependencies import (
    build_billing_repository,
    build_payment_service,
    build_server_repository,
    build_subscription_service,
    build_user_repository,
    session_provider,
)
from app.domain.enums import PaymentProvider, SubscriptionPlan

router = Router()


def _plan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Месяц", callback_data="purchase_plan:month"),
                InlineKeyboardButton(text="🗓 Год", callback_data="purchase_plan:year"),
            ]
        ]
    )


def _provider_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💎 CryptoBot", callback_data="purchase_provider:crypto"),
                InlineKeyboardButton(text="💳 YooKassa", callback_data="purchase_provider:yookassa"),
            ]
        ]
    )


@router.message(F.text == "💳 Купить подписку")
async def purchase_start(message: Message, state: FSMContext) -> None:
    async for session in session_provider():
        servers = await build_server_repository(session).list_active()
        if not servers:
            await message.answer("Нет доступных серверов.")
            return
        lines = [f"{s.id}. {s.name}" for s in servers]
        await message.answer("Выберите сервер, отправьте ID:\n" + "\n".join(lines))
        await state.set_state(PurchaseFlow.choosing_server)
        break


@router.message(PurchaseFlow.choosing_server)
async def purchase_server(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.isdigit():
        await message.answer("Введите ID сервера числом.")
        return
    await state.update_data(server_id=int(message.text))
    await state.set_state(PurchaseFlow.choosing_plan)
    await message.answer("Выберите план:", reply_markup=_plan_keyboard())


@router.callback_query(PurchaseFlow.choosing_plan, F.data.startswith("purchase_plan:"))
async def purchase_plan_callback(callback: CallbackQuery, state: FSMContext) -> None:
    raw_plan = callback.data.split(":", maxsplit=1)[1]
    if raw_plan not in {"month", "year"}:
        await callback.answer("Некорректный план", show_alert=True)
        return
    await state.update_data(plan=raw_plan)
    await state.set_state(PurchaseFlow.choosing_provider)
    await callback.message.answer(
        "Выберите провайдера оплаты:",
        reply_markup=_provider_keyboard(),
    )
    await callback.answer()


@router.message(PurchaseFlow.choosing_plan)
async def purchase_plan(message: Message, state: FSMContext) -> None:
    if message.text not in {"month", "year", "месяц", "год"}:
        await message.answer("Нажмите кнопку: «📅 Месяц» или «🗓 Год».")
        return
    normalized_plan = "month" if message.text in {"month", "месяц"} else "year"
    await state.update_data(plan=normalized_plan)
    await state.set_state(PurchaseFlow.choosing_provider)
    await message.answer(
        "Выберите провайдера оплаты:",
        reply_markup=_provider_keyboard(),
    )


@router.callback_query(PurchaseFlow.choosing_provider, F.data.startswith("purchase_provider:"))
async def purchase_provider_callback(callback: CallbackQuery, state: FSMContext) -> None:
    provider_input = callback.data.split(":", maxsplit=1)[1].strip().lower()
    if provider_input == "yookassa":
        await callback.message.answer(
            "YooKassa временно недоступна. Выберите, пожалуйста, 💎 CryptoBot.",
            reply_markup=_provider_keyboard(),
        )
        await callback.answer()
        return
    if provider_input != "crypto":
        await callback.answer("Некорректный провайдер", show_alert=True)
        return
    await callback.answer()
    await _create_crypto_invoice_from_state(callback.message, state)


@router.message(PurchaseFlow.choosing_provider)
async def purchase_provider(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return
    provider_input = message.text.strip().lower()
    if provider_input == "yookassa":
        await message.answer(
            "YooKassa временно недоступна. Выберите, пожалуйста, 💎 CryptoBot.",
            reply_markup=_provider_keyboard(),
        )
        return
    if provider_input not in {"crypto", "cryptobot", "💎 cryptobot"}:
        await message.answer(
            "Нажмите кнопку провайдера: 💎 CryptoBot или 💳 YooKassa.",
            reply_markup=_provider_keyboard(),
        )
        return
    await _create_crypto_invoice_from_state(message, state)


async def _create_crypto_invoice_from_state(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    server_id = int(data["server_id"])
    plan = SubscriptionPlan.MONTH if data["plan"] == "month" else SubscriptionPlan.YEAR

    async for session in session_provider():
        user_repo = build_user_repository(session)
        server_repo = build_server_repository(session)
        payment_service = build_payment_service(session)

        user = await user_repo.get_or_create(message.from_user.id, message.from_user.username)
        server = await server_repo.get_by_id(server_id)
        if server is None:
            await message.answer("Сервер не найден")
            await state.clear()
            return

        invoice, pay_url = await payment_service.create_crypto_invoice(user.id, server.id, plan)
        await session.commit()
        await message.answer(
            f"Crypto счет: {invoice.provider_invoice_id}\n"
            f"Сумма к оплате: {invoice.amount_due_provider}\n"
            f"Курс зафиксирован: {invoice.locked_rate}\n"
            f"Оплатить: {pay_url}"
        )
        await state.clear()
        break


@router.message(F.text == "📦 Моя подписка")
async def my_subscription(message: Message) -> None:
    if message.from_user is None:
        return
    async for session in session_provider():
        user = await build_user_repository(session).get_by_telegram_id(message.from_user.id)
        if user is None:
            await message.answer("Подписка не найдена")
            return
        sub = await build_subscription_service(session).billing_repo.get_active_subscription(user.id)
        if sub is None:
            await message.answer("Активной подписки нет")
            return
        await message.answer(
            f"План: {sub.plan.value}\n"
            f"Активна до: {sub.ends_at:%Y-%m-%d %H:%M UTC}"
        )
        accounts = await build_billing_repository(session).list_active_accounts_by_user(user.id)
        if accounts and accounts[0].subscription_url:
            await message.answer(f"Ссылка для подключения:\n{accounts[0].subscription_url}")
        break
