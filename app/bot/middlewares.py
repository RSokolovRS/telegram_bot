from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class SimpleRateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self.buckets: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[object]],
        event: TelegramObject,
        data: dict,
    ) -> object:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.time()
        window_start = now - 60
        self.buckets[user_id] = [t for t in self.buckets[user_id] if t > window_start]
        if len(self.buckets[user_id]) >= self.limit:
            await event.answer("Слишком много запросов. Попробуйте через минуту.")
            return None
        self.buckets[user_id].append(now)
        return await handler(event, data)
