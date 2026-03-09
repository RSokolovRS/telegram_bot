from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.fsm.states import PurchaseFlow
from app.dependencies import (
    build_payment_service,
    build_server_repository,
    build_subscription_service,
    build_user_repository,
    session_provider,
)
from app.domain.enums import PaymentProvider, SubscriptionPlan

router = Router()


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
    await message.answer("Выберите план: month или year")


@router.message(PurchaseFlow.choosing_plan)
async def purchase_plan(message: Message, state: FSMContext) -> None:
    if message.text not in {"month", "year"}:
        await message.answer("Введите month или year")
        return
    await state.update_data(plan=message.text)
    await state.set_state(PurchaseFlow.choosing_provider)
    await message.answer("Выберите провайдера оплаты: yookassa или crypto")


@router.message(PurchaseFlow.choosing_provider)
async def purchase_provider(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return
    provider_input = message.text.strip().lower()
    if provider_input not in {"yookassa", "crypto"}:
        await message.answer("Введите yookassa или crypto")
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

        if provider_input == PaymentProvider.YOOKASSA.value:
            invoice, pay_url = await payment_service.create_yookassa_invoice(user.id, server.id, plan)
            await session.commit()
            await message.answer(
                f"Счет создан: {invoice.provider_invoice_id}\n"
                f"Сумма: {invoice.amount_rub} RUB\n"
                f"Оплатить: {pay_url}"
            )
        else:
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
        break
