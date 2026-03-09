from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Invoice, Payment, Subscription, Trial, VpnAccount
from app.domain.enums import InvoiceStatus, PaymentStatus, SubscriptionStatus


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_trial_by_user_id(self, user_id: int) -> Trial | None:
        result = await self.session.execute(select(Trial).where(Trial.user_id == user_id))
        return result.scalar_one_or_none()

    async def create_trial(self, trial: Trial) -> Trial:
        self.session.add(trial)
        await self.session.flush()
        return trial

    async def get_active_subscription(self, user_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_subscription(self, subscription: Subscription) -> Subscription:
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_vpn_account(self, user_id: int, server_id: int) -> VpnAccount | None:
        result = await self.session.execute(
            select(VpnAccount).where(VpnAccount.user_id == user_id, VpnAccount.server_id == server_id)
        )
        return result.scalar_one_or_none()

    async def create_vpn_account(self, account: VpnAccount) -> VpnAccount:
        self.session.add(account)
        await self.session.flush()
        return account

    async def create_invoice(self, invoice: Invoice) -> Invoice:
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def get_invoice_by_provider_id(self, provider_invoice_id: str) -> Invoice | None:
        result = await self.session.execute(
            select(Invoice).where(Invoice.provider_invoice_id == provider_invoice_id)
        )
        return result.scalar_one_or_none()

    async def set_invoice_status(self, invoice: Invoice, status: InvoiceStatus) -> None:
        invoice.status = status
        await self.session.flush()

    async def create_payment(self, payment: Payment) -> Payment:
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_payment_by_provider_payment_id(self, provider_payment_id: str) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.provider_payment_id == provider_payment_id)
        )
        return result.scalar_one_or_none()

    async def list_trials_to_notify(self, now: datetime) -> list[Trial]:
        result = await self.session.execute(
            select(Trial).where(Trial.ends_at <= now, Trial.notified_end.is_(False))
        )
        return list(result.scalars().all())

    async def list_trials_to_delete(self, now: datetime) -> list[Trial]:
        result = await self.session.execute(
            select(Trial).where(Trial.ends_at <= now, Trial.deleted_after_grace.is_(False))
        )
        return list(result.scalars().all())

    async def list_subscriptions_to_notify(self, now: datetime) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.ends_at <= now,
                Subscription.notified_expiry.is_(False),
            )
        )
        return list(result.scalars().all())

    async def list_expired_subscriptions(self, now: datetime) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.ends_at <= now,
            )
        )
        return list(result.scalars().all())

    async def list_active_accounts_by_user(self, user_id: int) -> list[VpnAccount]:
        result = await self.session.execute(
            select(VpnAccount).where(VpnAccount.user_id == user_id, VpnAccount.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def mark_subscription_expired(self, subscription: Subscription) -> None:
        subscription.status = SubscriptionStatus.EXPIRED
        await self.session.flush()

    async def mark_trial_notified(self, trial: Trial) -> None:
        trial.notified_end = True
        await self.session.flush()

    async def mark_trial_deleted(self, trial: Trial) -> None:
        trial.deleted_after_grace = True
        await self.session.flush()

    async def mark_subscription_notified(self, subscription: Subscription) -> None:
        subscription.notified_expiry = True
        await self.session.flush()

    async def mark_account_inactive(self, account: VpnAccount) -> None:
        account.is_active = False
        await self.session.flush()

    async def has_success_payment_for_user_since(self, user_id: int, start: datetime) -> bool:
        result = await self.session.execute(
            select(Payment.id).where(
                Payment.user_id == user_id,
                Payment.status == PaymentStatus.SUCCEEDED,
                Payment.created_at >= start,
            )
        )
        return result.first() is not None
