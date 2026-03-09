from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db.models import Trial, VpnAccount
from app.repositories.billing import BillingRepository
from app.services.sui_service import SuiService


class TrialService:
    def __init__(self, billing_repo: BillingRepository, sui_service: SuiService) -> None:
        self.billing_repo = billing_repo
        self.sui_service = sui_service

    async def issue_trial(self, user_id: int, telegram_id: int, server_id: int, server) -> Trial:
        existing = await self.billing_repo.get_trial_by_user_id(user_id)
        if existing is not None:
            raise ValueError("Триал уже был выдан ранее")

        starts_at = datetime.now(timezone.utc)
        ends_at = starts_at + timedelta(days=settings.trial_days)
        trial = Trial(user_id=user_id, server_id=server_id, started_at=starts_at, ends_at=ends_at)
        await self.billing_repo.create_trial(trial)

        client_name = f"trial-{telegram_id}"
        account_result = await self.sui_service.create_account(server, client_name, ends_at)
        account = VpnAccount(
            user_id=user_id,
            server_id=server_id,
            sui_client_id=account_result["client_id"],
            subscription_url=account_result["subscription_url"],
            is_active=True,
        )
        await self.billing_repo.create_vpn_account(account)
        return trial
