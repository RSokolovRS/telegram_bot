from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4


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
