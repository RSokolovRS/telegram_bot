from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.db.models import Server
from app.integrations.sui_client import SUIClient, SuiCredentials


class SuiService:
    @staticmethod
    def _parse_inbound_ids(server: Server) -> list[int]:
        raw = (getattr(server, "inbound_ids", "") or "").strip()
        if raw:
            out: list[int] = []
            for part in raw.split(","):
                part = part.strip()
                if not part:
                    continue
                out.append(int(part))
            if out:
                return out
        env_raw = settings.sui_inbound_ids.strip()
        if env_raw:
            out: list[int] = []
            for part in env_raw.split(","):
                part = part.strip()
                if not part:
                    continue
                out.append(int(part))
            if out:
                return out
        return [int(server.inbound_id)]

    async def create_account(self, server: Server, client_name: str, expires_at: datetime) -> dict[str, str]:
        inbound_ids = self._parse_inbound_ids(server)
        creds = SuiCredentials(
            base_url=server.base_url,
            username=server.username,
            password=server.password,
            inbound_id=inbound_ids[0],
            path_prefix=server.panel_path_prefix or settings.sui_default_path_prefix,
            panel_base_path=settings.sui_panel_base_path,
            api_token=settings.sui_api_token,
        )
        client = SUIClient(credentials=creds, timeout=settings.sui_request_timeout)
        try:
            expires_ms = int(expires_at.astimezone(timezone.utc).timestamp() * 1000)
            return await client.create_hysteria2_client(
                email=client_name,
                expire_timestamp_ms=expires_ms,
                max_devices=2,
                inbound_ids=inbound_ids,
            )
        finally:
            await client.close()

    async def delete_account(self, server: Server, client_name: str) -> None:
        inbound_ids = self._parse_inbound_ids(server)
        creds = SuiCredentials(
            base_url=server.base_url,
            username=server.username,
            password=server.password,
            inbound_id=inbound_ids[0],
            path_prefix=server.panel_path_prefix or settings.sui_default_path_prefix,
            panel_base_path=settings.sui_panel_base_path,
            api_token=settings.sui_api_token,
        )
        client = SUIClient(credentials=creds, timeout=settings.sui_request_timeout)
        try:
            await client.delete_hysteria2_client(email=client_name, inbound_ids=inbound_ids)
        finally:
            await client.close()
