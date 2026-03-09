from __future__ import annotations

from app.domain.enums import TicketAuthorRole
from app.repositories.support import SupportRepository


class SupportService:
    def __init__(self, support_repo: SupportRepository) -> None:
        self.support_repo = support_repo

    async def open_ticket(self, user_id: int, telegram_id: int, text: str) -> int:
        thread = await self.support_repo.create_thread(user_id)
        await self.support_repo.add_message(
            thread_id=thread.id,
            author_role=TicketAuthorRole.USER,
            author_telegram_id=telegram_id,
            text=text,
        )
        return thread.id

    async def admin_reply(self, thread_id: int, admin_telegram_id: int, text: str) -> bool:
        thread = await self.support_repo.get_thread(thread_id)
        if thread is None:
            return False
        await self.support_repo.add_message(
            thread_id=thread.id,
            author_role=TicketAuthorRole.ADMIN,
            author_telegram_id=admin_telegram_id,
            text=text,
        )
        return True

    async def close_ticket(self, thread_id: int) -> bool:
        thread = await self.support_repo.get_thread(thread_id)
        if thread is None:
            return False
        await self.support_repo.close_thread(thread)
        return True
