from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.db.models import Server
from app.integrations.sui_client import SUIClient, SuiCredentials


class SuiService:
    async def create_account(self, server: Server, client_name: str, expires_at: datetime) -> dict[str, str]:
        creds = SuiCredentials(
            base_url=server.base_url,
            username=server.username,
            password=server.password,
            inbound_id=server.inbound_id,
            path_prefix=server.panel_path_prefix or settings.sui_default_path_prefix,
        )
        client = SUIClient(credentials=creds, timeout=settings.sui_request_timeout)
        try:
            expires_ms = int(expires_at.astimezone(timezone.utc).timestamp() * 1000)
            return await client.create_hysteria2_client(
                email=client_name,
                expire_timestamp_ms=expires_ms,
                max_devices=2,
            )
        finally:
            await client.close()

    async def delete_account(self, server: Server, client_name: str) -> None:
        creds = SuiCredentials(
            base_url=server.base_url,
            username=server.username,
            password=server.password,
            inbound_id=server.inbound_id,
            path_prefix=server.panel_path_prefix or settings.sui_default_path_prefix,
        )
        client = SUIClient(credentials=creds, timeout=settings.sui_request_timeout)
        try:
            await client.delete_hysteria2_client(email=client_name)
        finally:
            await client.close()
