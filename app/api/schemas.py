from __future__ import annotations

from pydantic import BaseModel


class YooKassaWebhookObject(BaseModel):
    id: str
    status: str
    metadata: dict[str, str] | None = None


class YooKassaWebhookPayload(BaseModel):
    type: str
    event: str
    object: YooKassaWebhookObject


class CryptoWebhookPayload(BaseModel):
    invoice_id: str
    status: str
    tx_id: str | None = None
