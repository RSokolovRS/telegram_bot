from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class YooKassaPaymentResult:
    payment_id: str
    confirmation_url: str
    status: str


class YooKassaClient:
    def __init__(self, shop_id: str, secret_key: str, timeout: int = 15) -> None:
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.base_url = "https://api.yookassa.ru/v3"
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()

    def _auth_header(self) -> str:
        token = base64.b64encode(f"{self.shop_id}:{self.secret_key}".encode("utf-8")).decode("utf-8")
        return f"Basic {token}"

    async def create_payment(
        self,
        amount_rub: int,
        description: str,
        return_url: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> YooKassaPaymentResult:
        payload = {
            "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description,
            "metadata": metadata,
        }
        response = await self.client.post(
            f"{self.base_url}/payments",
            headers={
                "Authorization": self._auth_header(),
                "Idempotence-Key": idempotency_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return YooKassaPaymentResult(
            payment_id=data["id"],
            confirmation_url=data["confirmation"]["confirmation_url"],
            status=data["status"],
        )

    async def get_payment(self, payment_id: str) -> dict:
        response = await self.client.get(
            f"{self.base_url}/payments/{payment_id}",
            headers={"Authorization": self._auth_header()},
        )
        response.raise_for_status()
        return response.json()
