from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.session import dispose_engine, get_session_factory, init_db
from app.queue.inprocess import InProcessQueue
from app.services.bootstrap import ensure_bootstrap_admin
from app.services.seed import seed_demo

logger = logging.getLogger("agenthub")


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        await ensure_bootstrap_admin(session)
        if settings.seed_demo_data:
            await seed_demo(session)

    queue = InProcessQueue()
    queue.start()
    logger.info("AgentHub started in %s mode", settings.app_mode)
    try:
        yield
    finally:
        await queue.stop()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AgentHub API",
        version=settings.version,
        description="AI agent management platform — local (SQLite, in-process) and docker contours",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
