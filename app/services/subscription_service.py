from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import Subscription, VpnAccount
from app.domain.enums import SubscriptionPlan
from app.repositories.billing import BillingRepository
from app.services.sui_service import SuiService


class SubscriptionService:
    def __init__(self, billing_repo: BillingRepository, sui_service: SuiService) -> None:
        self.billing_repo = billing_repo
        self.sui_service = sui_service

    async def activate_subscription(
        self,
        user_id: int,
        telegram_id: int,
        server_id: int,
        server,
        plan: SubscriptionPlan,
    ) -> Subscription:
        now = datetime.now(timezone.utc)
        duration = timedelta(days=30) if plan == SubscriptionPlan.MONTH else timedelta(days=365)
        ends_at = now + duration

        active = await self.billing_repo.get_active_subscription(user_id)
        if active is not None:
            active.ends_at = max(active.ends_at, now) + duration
            return active

        subscription = Subscription(
            user_id=user_id,
            server_id=server_id,
            plan=plan,
            starts_at=now,
            ends_at=ends_at,
        )
        await self.billing_repo.create_subscription(subscription)

        account = await self.billing_repo.get_vpn_account(user_id, server_id)
        client_name = f"sub-{telegram_id}"
        if account is None:
            account_result = await self.sui_service.create_account(server, client_name, ends_at)
            new_account = VpnAccount(
                user_id=user_id,
                server_id=server_id,
                sui_client_id=account_result["client_id"],
                subscription_url=account_result["subscription_url"],
                is_active=True,
            )
            await self.billing_repo.create_vpn_account(new_account)
        else:
            account.is_active = True

        return subscription
