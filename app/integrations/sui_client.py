from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class SuiCredentials:
    base_url: str
    username: str
    password: str
    inbound_id: int
    path_prefix: str = "/sub/"


class SUIClient:
    def __init__(self, credentials: SuiCredentials, timeout: int = 15) -> None:
        self.credentials = credentials
        self.timeout = timeout
        self._client = httpx.AsyncClient(base_url=credentials.base_url, timeout=timeout)
        self._authenticated = False

    async def close(self) -> None:
        await self._client.aclose()

    async def authenticate(self) -> None:
        if self._authenticated:
            return
        payload = {"username": self.credentials.username, "password": self.credentials.password}
        response = await self._client.post("/login", json=payload)
        response.raise_for_status()
        self._authenticated = True

    async def create_hysteria2_client(
        self,
        email: str,
        expire_timestamp_ms: int,
        max_devices: int = 2,
    ) -> dict[str, str]:
        await self.authenticate()
        payload = {
            "id": self.credentials.inbound_id,
            "settings": {
                "clients": [
                    {
                        "email": email,
                        "up": 0,
                        "down": 0,
                        "total": 0,
                        "limitIp": max_devices,
                        "expiryTime": expire_timestamp_ms,
                        "enable": True,
                    }
                ]
            },
        }
        response = await self._client.post("/panel/api/inbounds/addClient", json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise RuntimeError(f"s-ui addClient failed: {data}")

        client_id = email
        sub_url = f"{self.credentials.base_url.rstrip('/')}{self.credentials.path_prefix}{client_id}"
        return {"client_id": client_id, "subscription_url": sub_url}

    async def delete_hysteria2_client(self, email: str) -> None:
        await self.authenticate()
        payload = {"id": self.credentials.inbound_id, "clientId": email}
        response = await self._client.post("/panel/api/inbounds/delClient", json=payload)
        response.raise_for_status()

    async def get_hysteria2_client(self, email: str) -> dict | None:
        await self.authenticate()
        response = await self._client.get("/panel/api/inbounds/list")
        response.raise_for_status()
        data = response.json()
        for inbound in data.get("obj", []):
            settings = inbound.get("settings") or {}
            for client in settings.get("clients", []):
                if client.get("email") == email:
                    return client
        return None
