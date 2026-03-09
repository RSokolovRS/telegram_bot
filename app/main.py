from __future__ import annotations

import asyncio

import uvicorn

from app.api.app import create_fastapi_app
from app.bot.app import create_bot, create_dispatcher
from app.core.config import settings
from app.core.logging import setup_logging
from app.scheduler.scheduler import create_scheduler


async def run_bot() -> None:
    bot = create_bot()
    dp = create_dispatcher()
    scheduler = create_scheduler(bot)
    scheduler.start()
    await dp.start_polling(bot)


async def run_api() -> None:
    app = create_fastapi_app()
    config = uvicorn.Config(app=app, host=settings.api_host, port=settings.api_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_all() -> None:
    await asyncio.gather(run_api(), run_bot())


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_all())
