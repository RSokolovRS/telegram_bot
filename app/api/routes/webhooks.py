from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CryptoWebhookPayload, YooKassaWebhookPayload
from app.core.config import settings
from app.core.security import verify_hmac_signature
from app.db.session import get_session
from app.dependencies import build_payment_service, build_server_repository, build_subscription_service, build_user_repository

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _is_ip_allowed(client_ip: str | None) -> bool:
    if not settings.yoo_kassa_webhook_ip_allowlist.strip():
        return True
    allowed = {ip.strip() for ip in settings.yoo_kassa_webhook_ip_allowlist.split(",") if ip.strip()}
    return client_ip in allowed


@router.post("/yookassa")
async def yookassa_webhook(
    payload: YooKassaWebhookPayload,
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if not _is_ip_allowed(request.client.host if request.client else None):
        raise HTTPException(status_code=403, detail="ip is not allowed")

    raw = await request.body()
    if x_webhook_signature:
        if not verify_hmac_signature(raw, settings.webhook_shared_secret, x_webhook_signature):
            raise HTTPException(status_code=401, detail="invalid signature")

    if payload.object.status != "succeeded":
        return {"status": "ignored"}

    service = build_payment_service(session)
    invoice = await service.mark_invoice_paid(payload.object.id, payload.object.id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    user = await build_user_repository(session).get_by_id(invoice.user_id)
    server = await build_server_repository(session).get_by_id(invoice.server_id)
    if user is None or server is None:
        raise HTTPException(status_code=404, detail="invoice references invalid user/server")

    await build_subscription_service(session).activate_subscription(
        user_id=user.id,
        telegram_id=user.telegram_id,
        server_id=server.id,
        server=server,
        plan=invoice.subscription_plan,
    )

    await session.commit()
    return {"status": "ok"}


@router.post("/crypto")
async def crypto_webhook(
    payload: CryptoWebhookPayload,
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    raw = await request.body()
    if x_webhook_signature:
        if not verify_hmac_signature(raw, settings.webhook_shared_secret, x_webhook_signature):
            raise HTTPException(status_code=401, detail="invalid signature")

    if payload.status != "paid":
        return {"status": "ignored"}

    payment_id = payload.tx_id or payload.invoice_id
    service = build_payment_service(session)
    invoice = await service.mark_invoice_paid(payload.invoice_id, payment_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    user = await build_user_repository(session).get_by_id(invoice.user_id)
    server = await build_server_repository(session).get_by_id(invoice.server_id)
    if user is None or server is None:
        raise HTTPException(status_code=404, detail="invoice references invalid user/server")

    await build_subscription_service(session).activate_subscription(
        user_id=user.id,
        telegram_id=user.telegram_id,
        server_id=server.id,
        server=server,
        plan=invoice.subscription_plan,
    )

    await session.commit()
    return {"status": "ok"}
