from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Server
from app.domain.enums import ServerStatus


class ServerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[Server]:
        result = await self.session.execute(
            select(Server).where(Server.status == ServerStatus.ACTIVE).order_by(Server.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, server_id: int) -> Server | None:
        result = await self.session.execute(select(Server).where(Server.id == server_id))
        return result.scalar_one_or_none()
