from __future__ import annotations

from uuid import uuid4

from app.core.config import settings
from app.db.models import Invoice, Payment
from app.domain.enums import InvoiceStatus, PaymentProvider, PaymentStatus, SubscriptionPlan
from app.integrations.crypto_provider import CryptoProvider
from app.integrations.yookassa_client import YooKassaClient
from app.repositories.billing import BillingRepository


class PaymentService:
    def __init__(
        self,
        billing_repo: BillingRepository,
        yookassa_client: YooKassaClient,
        crypto_provider: CryptoProvider,
    ) -> None:
        self.billing_repo = billing_repo
        self.yookassa_client = yookassa_client
        self.crypto_provider = crypto_provider

    @staticmethod
    def plan_price(plan: SubscriptionPlan) -> int:
        return settings.plan_month_price_rub if plan == SubscriptionPlan.MONTH else settings.plan_year_price_rub

    async def create_yookassa_invoice(
        self,
        user_id: int,
        server_id: int,
        plan: SubscriptionPlan,
    ) -> tuple[Invoice, str]:
        raise RuntimeError("YooKassa is temporarily disabled")
        amount = self.plan_price(plan)
        idempotency_key = str(uuid4())
        result = await self.yookassa_client.create_payment(
            amount_rub=amount,
            description=f"VPN подписка ({plan.value})",
            return_url=settings.yoo_kassa_return_url,
            idempotency_key=idempotency_key,
            metadata={"user_id": str(user_id), "plan": plan.value},
        )

        invoice = Invoice(
            user_id=user_id,
            server_id=server_id,
            subscription_plan=plan,
            provider=PaymentProvider.YOOKASSA,
            provider_invoice_id=result.payment_id,
            amount_rub=amount,
            status=InvoiceStatus.PENDING,
        )
        await self.billing_repo.create_invoice(invoice)
        return invoice, result.confirmation_url

    async def create_crypto_invoice(
        self,
        user_id: int,
        server_id: int,
        plan: SubscriptionPlan,
    ) -> tuple[Invoice, str]:
        amount = self.plan_price(plan)
        result = await self.crypto_provider.create_invoice(amount)
        invoice = Invoice(
            user_id=user_id,
            server_id=server_id,
            subscription_plan=plan,
            provider=PaymentProvider.CRYPTO,
            provider_invoice_id=result.invoice_id,
            amount_rub=amount,
            amount_due_provider=result.amount_due,
            locked_rate=result.locked_rate,
            status=InvoiceStatus.PENDING,
            expires_at=result.expires_at,
        )
        await self.billing_repo.create_invoice(invoice)
        return invoice, result.pay_url

    async def mark_invoice_paid(self, provider_invoice_id: str, provider_payment_id: str) -> Invoice | None:
        invoice = await self.billing_repo.get_invoice_by_provider_id(provider_invoice_id)
        if invoice is None:
            return None
        if invoice.status == InvoiceStatus.PAID:
            return invoice

        await self.billing_repo.set_invoice_status(invoice, InvoiceStatus.PAID)
        payment = Payment(
            user_id=invoice.user_id,
            provider=invoice.provider,
            provider_payment_id=provider_payment_id,
            amount_rub=invoice.amount_rub,
            status=PaymentStatus.SUCCEEDED,
            idempotency_key=str(uuid4()),
        )
        await self.billing_repo.create_payment(payment)
        return invoice
