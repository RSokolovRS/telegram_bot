from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

from app.core.config import settings


@dataclass(slots=True)
class CryptoInvoiceResult:
    invoice_id: str
    amount_due: float
    locked_rate: float
    pay_url: str
    expires_at: datetime


class CryptoProvider(ABC):
    @abstractmethod
    async def create_invoice(self, amount_rub: int) -> CryptoInvoiceResult:
        raise NotImplementedError

    @abstractmethod
    async def get_invoice_status(self, invoice_id: str) -> str:
        raise NotImplementedError


class MockCryptoProvider(CryptoProvider):
    def __init__(self, locked_rate: float) -> None:
        self.locked_rate = locked_rate
        self._statuses: dict[str, str] = {}

    async def create_invoice(self, amount_rub: int) -> CryptoInvoiceResult:
        invoice_id = f"mock-{uuid4()}"
        amount_due = round(amount_rub / self.locked_rate, 8)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        self._statuses[invoice_id] = "pending"
        return CryptoInvoiceResult(
            invoice_id=invoice_id,
            amount_due=amount_due,
            locked_rate=self.locked_rate,
            pay_url=f"https://mock-crypto.local/pay/{invoice_id}",
            expires_at=expires_at,
        )

    async def get_invoice_status(self, invoice_id: str) -> str:
        return self._statuses.get(invoice_id, "pending")

    async def mark_paid(self, invoice_id: str) -> None:
        self._statuses[invoice_id] = "paid"


class CryptoBotProvider(CryptoProvider):
    def __init__(self, token: str, api_base: str) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")

    async def create_invoice(self, amount_rub: int) -> CryptoInvoiceResult:
        payload = {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": str(amount_rub),
            "description": "VPN подписка",
            "expires_in": 1800,
        }
        data = await self._call("createInvoice", payload)

        invoice_id = str(data.get("invoice_id") or data.get("id") or "")
        if not invoice_id:
            raise RuntimeError("CryptoBot createInvoice returned empty invoice_id")

        pay_url = str(data.get("pay_url") or "")
        if not pay_url:
            raise RuntimeError("CryptoBot createInvoice returned empty pay_url")

        amount_due = self._to_float(data.get("pay_amount") or data.get("amount"))
        if amount_due is None:
            amount_due = round(amount_rub / settings.crypto_default_rate_rub, 8)

        locked_rate = self._to_float(data.get("rate"))
        if locked_rate is None and amount_due > 0:
            locked_rate = round(float(amount_rub) / amount_due, 8)
        if locked_rate is None:
            locked_rate = settings.crypto_default_rate_rub

        expires_at = self._parse_datetime(data.get("expiration_date"))
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        return CryptoInvoiceResult(
            invoice_id=invoice_id,
            amount_due=amount_due,
            locked_rate=locked_rate,
            pay_url=pay_url,
            expires_at=expires_at,
        )

    async def get_invoice_status(self, invoice_id: str) -> str:
        data = await self._call("getInvoices", {"invoice_ids": invoice_id})
        items: list[dict] = []
        if isinstance(data, dict):
            raw_items = data.get("items")
            if isinstance(raw_items, list):
                items = [item for item in raw_items if isinstance(item, dict)]
        elif isinstance(data, list):
            items = [item for item in data if isinstance(item, dict)]

        if not items:
            return "pending"

        status = str(items[0].get("status") or "pending").lower()
        if status in {"paid", "confirmed", "completed"}:
            return "paid"
        if status in {"expired", "cancelled", "canceled", "failed"}:
            return "expired"
        return "pending"

    async def _call(self, method: str, payload: dict[str, str]) -> dict | list:
        url = f"{self.api_base}/{method}"
        headers = {"Crypto-Pay-API-Token": self.token}
        timeout = httpx.Timeout(15.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        if not isinstance(body, dict):
            raise RuntimeError("CryptoBot response is not a JSON object")

        if not body.get("ok", False):
            error_msg = body.get("error") or body.get("description") or "unknown error"
            raise RuntimeError(f"CryptoBot API error: {error_msg}")

        result = body.get("result")
        if isinstance(result, (dict, list)):
            return result
        raise RuntimeError("CryptoBot response missing result")

    @staticmethod
    def _to_float(value: object) -> float | None:
        try:
            if value is None:
                return None
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            raw = str(value).strip()
            if not raw:
                return None
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None
