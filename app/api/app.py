from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.internal import router as internal_router
from app.api.routes.webhooks import router as webhooks_router


def create_fastapi_app() -> FastAPI:
    app = FastAPI(title="VPN Bot API", version="1.0.0")
    app.include_router(webhooks_router)
    app.include_router(internal_router)
    app.include_router(health_router)
    return app
