from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TicketMessage, TicketThread
from app.domain.enums import TicketAuthorRole, TicketStatus


class SupportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_thread(self, user_id: int) -> TicketThread:
        thread = TicketThread(user_id=user_id, status=TicketStatus.OPEN)
        self.session.add(thread)
        await self.session.flush()
        return thread

    async def add_message(
        self,
        thread_id: int,
        author_role: TicketAuthorRole,
        author_telegram_id: int,
        text: str,
    ) -> TicketMessage:
        message = TicketMessage(
            thread_id=thread_id,
            author_role=author_role,
            author_telegram_id=author_telegram_id,
            text=text,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_open_threads(self) -> list[TicketThread]:
        result = await self.session.execute(
            select(TicketThread).where(TicketThread.status == TicketStatus.OPEN).order_by(TicketThread.id)
        )
        return list(result.scalars().all())

    async def list_threads_by_user_id(self, user_id: int, limit: int = 5) -> list[TicketThread]:
        result = await self.session.execute(
            select(TicketThread)
            .where(TicketThread.user_id == user_id)
            .order_by(TicketThread.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_open_thread_by_user_id(self, user_id: int) -> TicketThread | None:
        result = await self.session.execute(
            select(TicketThread).where(
                TicketThread.user_id == user_id,
                TicketThread.status == TicketStatus.OPEN,
            ).order_by(TicketThread.id.desc())
        )
        return result.scalar_one_or_none()

    async def get_thread(self, thread_id: int) -> TicketThread | None:
        result = await self.session.execute(select(TicketThread).where(TicketThread.id == thread_id))
        return result.scalar_one_or_none()

    async def list_messages(self, thread_id: int, limit: int = 20) -> list[TicketMessage]:
        result = await self.session.execute(
            select(TicketMessage)
            .where(TicketMessage.thread_id == thread_id)
            .order_by(TicketMessage.id.desc())
            .limit(limit)
        )
        return list(reversed(list(result.scalars().all())))

    async def close_thread(self, thread: TicketThread) -> None:
        thread.status = TicketStatus.CLOSED
        thread.closed_at = datetime.now(timezone.utc)
        await self.session.flush()
