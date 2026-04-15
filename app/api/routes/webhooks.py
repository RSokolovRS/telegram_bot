from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import YooKassaWebhookPayload
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
    raise HTTPException(status_code=501, detail="YooKassa webhook is temporarily disabled")
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
    request: Request,
    crypto_pay_api_signature: str | None = Header(default=None, alias="Crypto-Pay-API-Signature"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    raw = await request.body()
    if not crypto_pay_api_signature:
        raise HTTPException(status_code=401, detail="missing signature")
    if not settings.crypto_bot_token.strip():
        raise HTTPException(status_code=500, detail="CryptoBot token is not configured")
    if not verify_hmac_signature(raw, settings.crypto_bot_token, crypto_pay_api_signature):
        raise HTTPException(status_code=401, detail="invalid signature")

    payload = await request.json()
    invoice_id, status, payment_id = _parse_crypto_webhook(payload)

    if not invoice_id:
        raise HTTPException(status_code=400, detail="invoice_id is missing")

    if status != "paid":
        return {"status": "ignored"}

    provider_payment_id = payment_id or invoice_id
    service = build_payment_service(session)
    invoice = await service.mark_invoice_paid(invoice_id, provider_payment_id)
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


def _parse_crypto_webhook(payload: Any) -> tuple[str | None, str, str | None]:
    if not isinstance(payload, dict):
        return None, "unknown", None

    # Legacy project payload: {invoice_id, status, tx_id}
    legacy_invoice_id = payload.get("invoice_id")
    legacy_status = payload.get("status")
    legacy_tx_id = payload.get("tx_id")
    if legacy_invoice_id is not None and legacy_status is not None:
        return str(legacy_invoice_id), str(legacy_status).lower(), str(legacy_tx_id) if legacy_tx_id else None

    # CryptoBot update payload shape:
    # {"update_type":"invoice_paid", "payload": {"invoice_id": 123, "status": "paid", ...}}
    update_type = str(payload.get("update_type") or payload.get("event") or "").lower()
    nested = payload.get("payload")
    if not isinstance(nested, dict):
        nested = payload.get("data")
    if not isinstance(nested, dict):
        nested = {}

    invoice_id = nested.get("invoice_id") or nested.get("id") or payload.get("invoice_id")
    status_raw = nested.get("status") or payload.get("status")
    if not status_raw and update_type in {"invoice_paid", "paid", "payment.succeeded"}:
        status_raw = "paid"

    tx_id = nested.get("tx_id") or nested.get("hash") or payload.get("tx_id")

    status = str(status_raw).lower() if status_raw else "unknown"
    return (str(invoice_id) if invoice_id is not None else None), status, (str(tx_id) if tx_id else None)
