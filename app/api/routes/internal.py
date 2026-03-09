from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import build_crypto_provider

router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.get("/crypto/invoices/{invoice_id}")
async def crypto_invoice_status(invoice_id: str) -> dict[str, str]:
    provider = build_crypto_provider()
    status = await provider.get_invoice_status(invoice_id)
    return {"invoice_id": invoice_id, "status": status}
