from __future__ import annotations

from dataclasses import dataclass
import json

import httpx


@dataclass(slots=True)
class SuiCredentials:
    base_url: str
    username: str
    password: str
    inbound_id: int
    path_prefix: str = "/sub/"
    panel_base_path: str = ""
    api_token: str = ""


class SUIClient:
    def __init__(self, credentials: SuiCredentials, timeout: int = 15) -> None:
        self.credentials = credentials
        self.timeout = timeout
        self._client = httpx.AsyncClient(base_url=credentials.base_url, timeout=timeout)
        self._authenticated = False

    def _with_panel_prefix(self, path: str) -> str:
        panel_base = (self.credentials.panel_base_path or "").strip()
        if panel_base and not panel_base.startswith("/"):
            panel_base = f"/{panel_base}"
        panel_base = panel_base.rstrip("/")

        endpoint = path if path.startswith("/") else f"/{path}"
        return f"{panel_base}{endpoint}" if panel_base else endpoint

    def _has_apiv2(self) -> bool:
        return bool(self.credentials.api_token.strip())

    async def close(self) -> None:
        await self._client.aclose()

    async def authenticate(self) -> None:
        if self._authenticated:
            return
        payload = {"username": self.credentials.username, "password": self.credentials.password}
        response = await self._client.post(self._with_panel_prefix("/login"), json=payload)
        response.raise_for_status()
        self._authenticated = True

    async def _apiv2_save(self, action: str, data: dict) -> dict:
        response = await self._client.post(
            self._with_panel_prefix("/apiv2/save"),
            headers={"Token": self.credentials.api_token},
            data={
                "object": "clients",
                "action": action,
                "data": json.dumps(data, ensure_ascii=False),
            },
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not body.get("success", False):
            raise RuntimeError(f"s-ui apiv2/save failed: {body}")
        return body

    async def _apiv2_clients(self) -> list[dict]:
        response = await self._client.get(
            self._with_panel_prefix("/apiv2/clients"),
            headers={"Token": self.credentials.api_token},
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not body.get("success", False):
            return []
        obj = body.get("obj")
        if isinstance(obj, dict):
            clients = obj.get("clients")
            if isinstance(clients, list):
                return [item for item in clients if isinstance(item, dict)]
        if isinstance(obj, list):
            return [item for item in obj if isinstance(item, dict)]
        return []

    @staticmethod
    def _normalize_inbounds(value: object) -> list[int]:
        if not isinstance(value, list):
            return []
        out: list[int] = []
        for item in value:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out

    async def create_hysteria2_client(
        self,
        email: str,
        expire_timestamp_ms: int,
        max_devices: int = 2,
        inbound_ids: list[int] | None = None,
    ) -> dict[str, str]:
        target_inbounds = inbound_ids or [self.credentials.inbound_id]
        if self._has_apiv2():
            # S-UI APIv2 (Token): avoid duplicate names.
            # If client already exists, use "edit" and extend expiry instead of creating another row.
            existing = next((item for item in await self._apiv2_clients() if item.get("name") == email), None)
            if existing is None:
                await self._apiv2_save(
                    action="new",
                    data={
                        "id": 0,
                        "enable": True,
                        "name": email,
                        "inbounds": target_inbounds,
                        "volume": 0,
                        "expiry": expire_timestamp_ms,
                        "down": 0,
                        "up": 0,
                        "desc": "",
                        "group": "",
                        "links": [],
                        # For s-ui 1.4.x, empty per-protocol JSON objects are accepted.
                        "config": {"hysteria2": {}, "vless": {}},
                    },
                )
            else:
                existing_id = int(existing.get("id", 0))
                existing_inbounds = self._normalize_inbounds(existing.get("inbounds"))
                merged_inbounds = sorted(set(existing_inbounds) | set(target_inbounds))
                current_expiry = int(existing.get("expiry", 0) or 0)
                new_expiry = max(current_expiry, expire_timestamp_ms)
                existing_down = int(existing.get("down", 0) or 0)
                existing_up = int(existing.get("up", 0) or 0)
                await self._apiv2_save(
                    action="edit",
                    data={
                        "id": existing_id,
                        "enable": bool(existing.get("enable", True)),
                        "name": email,
                        "inbounds": merged_inbounds,
                        "volume": int(existing.get("volume", 0) or 0),
                        "expiry": new_expiry,
                        "down": existing_down,
                        "up": existing_up,
                        "desc": str(existing.get("desc", "") or ""),
                        "group": str(existing.get("group", "") or ""),
                        "links": existing.get("links", []),
                        "config": existing.get("config", {"hysteria2": {}, "vless": {}})
                        if isinstance(existing.get("config"), dict)
                        else {"hysteria2": {}, "vless": {}},
                    },
                )
        else:
            # Legacy (x-ui/3x-ui-like) API
            await self.authenticate()
            for inbound_id in target_inbounds:
                payload = {
                    "id": inbound_id,
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
                response = await self._client.post(
                    self._with_panel_prefix("/panel/api/inbounds/addClient"), json=payload
                )
                response.raise_for_status()
                data = response.json()
                if not data.get("success"):
                    raise RuntimeError(f"s-ui addClient failed: {data}")

        client_id = email
        sub_url = f"{self.credentials.base_url.rstrip('/')}{self.credentials.path_prefix}{client_id}"
        return {"client_id": client_id, "subscription_url": sub_url}

    async def delete_hysteria2_client(self, email: str, inbound_ids: list[int] | None = None) -> None:
        target_inbounds = inbound_ids or [self.credentials.inbound_id]
        if self._has_apiv2():
            clients = await self._apiv2_clients()
            to_delete = [int(item["id"]) for item in clients if item.get("name") == email and "id" in item]
            for client_id in to_delete:
                await self._apiv2_save(action="del", data={"id": client_id})
            return

        await self.authenticate()
        for inbound_id in target_inbounds:
            payload = {"id": inbound_id, "clientId": email}
            response = await self._client.post(self._with_panel_prefix("/panel/api/inbounds/delClient"), json=payload)
            response.raise_for_status()

    async def get_hysteria2_client(self, email: str) -> dict | None:
        if self._has_apiv2():
            for item in await self._apiv2_clients():
                if item.get("name") == email:
                    return item
            return None

        await self.authenticate()
        response = await self._client.get(self._with_panel_prefix("/panel/api/inbounds/list"))
        response.raise_for_status()
        data = response.json()
        for inbound in data.get("obj", []):
            settings = inbound.get("settings") or {}
            for client in settings.get("clients", []):
                if client.get("email") == email:
                    return client
        return None
