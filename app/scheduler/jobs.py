from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.dependencies import build_billing_repository, build_server_repository, build_user_repository
from app.services.sui_service import SuiService

logger = logging.getLogger(__name__)


async def notify_finished_trials(bot: Bot) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        billing_repo = build_billing_repository(session)
        user_repo = build_user_repository(session)
        trials = await billing_repo.list_trials_to_notify(now)
        for trial in trials:
            user = await user_repo.get_by_id(trial.user_id)
            if user is None:
                continue
            await bot.send_message(
                user.telegram_id,
                "Ваш пробный период завершился. Оформите подписку, чтобы продолжить пользоваться VPN.",
            )
            await billing_repo.mark_trial_notified(trial)
        await session.commit()


async def delete_unpaid_after_trial(bot: Bot) -> None:
    now = datetime.now(timezone.utc) - timedelta(days=settings.trial_grace_days)
    async with AsyncSessionLocal() as session:
        billing_repo = build_billing_repository(session)
        server_repo = build_server_repository(session)
        user_repo = build_user_repository(session)
        sui_service = SuiService()

        trials = await billing_repo.list_trials_to_delete(now)
        for trial in trials:
            paid = await billing_repo.has_success_payment_for_user_since(trial.user_id, trial.ends_at)
            if paid:
                await billing_repo.mark_trial_deleted(trial)
                continue

            accounts = await billing_repo.list_active_accounts_by_user(trial.user_id)
            for account in accounts:
                server = await server_repo.get_by_id(account.server_id)
                if server is None:
                    continue
                await sui_service.delete_account(server, account.sui_client_id)
                await billing_repo.mark_account_inactive(account)

            await billing_repo.mark_trial_deleted(trial)
            user = await user_repo.get_by_id(trial.user_id)
            if user is not None:
                await bot.send_message(user.telegram_id, "Триал истек и доступ удален из-за отсутствия оплаты.")

        await session.commit()


async def notify_subscription_expiry(bot: Bot) -> None:
    boundary = datetime.now(timezone.utc) + timedelta(hours=settings.subscription_expiry_notify_hours)
    async with AsyncSessionLocal() as session:
        billing_repo = build_billing_repository(session)
        user_repo = build_user_repository(session)
        subs = await billing_repo.list_subscriptions_to_notify(boundary)
        for sub in subs:
            user = await user_repo.get_by_id(sub.user_id)
            if user is None:
                continue
            await bot.send_message(
                user.telegram_id,
                f"Подписка истекает {sub.ends_at:%Y-%m-%d %H:%M UTC}. Продлите заранее.",
            )
            await billing_repo.mark_subscription_notified(sub)
        await session.commit()


async def delete_expired_subscriptions(bot: Bot) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        billing_repo = build_billing_repository(session)
        server_repo = build_server_repository(session)
        user_repo = build_user_repository(session)
        sui_service = SuiService()

        subs = await billing_repo.list_expired_subscriptions(now)
        for sub in subs:
            accounts = await billing_repo.list_active_accounts_by_user(sub.user_id)
            for account in accounts:
                if account.server_id != sub.server_id:
                    continue
                server = await server_repo.get_by_id(account.server_id)
                if server is None:
                    continue
                await sui_service.delete_account(server, account.sui_client_id)
                await billing_repo.mark_account_inactive(account)
            await billing_repo.mark_subscription_expired(sub)

            user = await user_repo.get_by_id(sub.user_id)
            if user is not None:
                await bot.send_message(user.telegram_id, "Подписка завершена, VPN-доступ удален.")

        await session.commit()


async def check_sui_servers_health() -> None:
    logger.info("s-ui health check ping completed")
