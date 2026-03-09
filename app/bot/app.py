from __future__ import annotations

from aiogram import Bot, Dispatcher

from app.bot.handlers import common, subscription, support, trial
from app.bot.middlewares import SimpleRateLimitMiddleware
from app.core.config import settings


def create_bot() -> Bot:
    return Bot(token=settings.bot_token)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.middleware(SimpleRateLimitMiddleware(limit_per_minute=settings.bot_rate_limit_per_minute))
    dp.include_router(common.router)
    dp.include_router(trial.router)
    dp.include_router(subscription.router)
    dp.include_router(support.router)
    return dp
