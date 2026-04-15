from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations.crypto_provider import CryptoBotProvider, CryptoProvider, MockCryptoProvider
from app.integrations.yookassa_client import YooKassaClient
from app.repositories.billing import BillingRepository
from app.repositories.servers import ServerRepository
from app.repositories.support import SupportRepository
from app.repositories.users import UserRepository
from app.services.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService
from app.services.sui_service import SuiService
from app.services.support_service import SupportService
from app.services.trial_service import TrialService

_crypto_provider: CryptoProvider | None = None
_yookassa_client: YooKassaClient | None = None


async def session_provider() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def build_crypto_provider() -> CryptoProvider:
    global _crypto_provider
    if _crypto_provider is None:
        provider_name = settings.crypto_provider.strip().lower()
        if provider_name == "cryptobot":
            if not settings.crypto_bot_token.strip():
                raise RuntimeError("CRYPTO_PROVIDER=cryptobot requires CRYPTO_BOT_TOKEN")
            _crypto_provider = CryptoBotProvider(
                token=settings.crypto_bot_token,
                api_base=settings.crypto_bot_api_base,
            )
        else:
            _crypto_provider = MockCryptoProvider(locked_rate=settings.crypto_default_rate_rub)
    return _crypto_provider


def build_yookassa_client() -> YooKassaClient:
    global _yookassa_client
    if _yookassa_client is None:
        _yookassa_client = YooKassaClient(
            shop_id=settings.yoo_kassa_shop_id,
            secret_key=settings.yoo_kassa_secret_key,
        )
    return _yookassa_client


def build_trial_service(session: AsyncSession) -> TrialService:
    return TrialService(BillingRepository(session), SuiService())


def build_subscription_service(session: AsyncSession) -> SubscriptionService:
    return SubscriptionService(BillingRepository(session), SuiService())


def build_payment_service(session: AsyncSession) -> PaymentService:
    return PaymentService(
        BillingRepository(session),
        build_yookassa_client(),
        build_crypto_provider(),
    )


def build_support_service(session: AsyncSession) -> SupportService:
    return SupportService(SupportRepository(session))


def build_user_repository(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


def build_server_repository(session: AsyncSession) -> ServerRepository:
    return ServerRepository(session)


def build_billing_repository(session: AsyncSession) -> BillingRepository:
    return BillingRepository(session)
