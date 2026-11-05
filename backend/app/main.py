from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.rate_limit import RateLimiter
from app.db.session import dispose_engine, get_session_factory, init_db
from app.queue.arq import ArqTaskQueue
from app.queue.inprocess import InProcessQueue
from app.queue.runtime import set_queue
from app.scheduler import tick
from app.services.bootstrap import ensure_bootstrap_admin
from app.services.seed import seed_demo
from app.services.tasks import execute_task

logger = logging.getLogger("agenthub")


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.is_docker_mode and (
        settings.jwt_secret.startswith("dev-only") or settings.jwt_secret in {"change-me-in-production", ""}
    ):
        raise RuntimeError("APP_MODE=docker requires a strong JWT_SECRET")
    configure_logging()
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        await ensure_bootstrap_admin(session)
        if settings.seed_demo_data:
            await seed_demo(session)

    queue = ArqTaskQueue(settings.redis_url) if settings.is_docker_mode else InProcessQueue()
    if isinstance(queue, InProcessQueue):
        queue.register("execute_task", lambda payload: execute_task(payload["task_id"]))
    set_queue(queue)
    queue.start()
    scheduler_stopping = False

    async def scheduler_loop() -> None:
        while not scheduler_stopping:
            await tick()
            await asyncio.sleep(1)

    scheduler_task = asyncio.create_task(scheduler_loop(), name="agenthub-scheduler")
    logger.info("AgentHub started in %s mode", settings.app_mode)
    try:
        yield
    finally:
        scheduler_stopping = True
        scheduler_task.cancel()
        await asyncio.gather(scheduler_task, return_exceptions=True)
        await queue.stop()
        await app.state.rate_limiter.close()
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
    rate_limiter = RateLimiter(settings.redis_url if settings.is_docker_mode else None)
    app.state.rate_limiter = rate_limiter

    @app.middleware("http")
    async def observability_middleware(request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or str(uuid4())
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        rate_limit = None
        if request.method == "POST":
            if request.url.path == "/api/v1/auth/login" or request.url.path == "/api/v1/auth/refresh":
                rate_limit = ("auth", settings.auth_rate_limit_per_minute)
            elif request.url.path.startswith("/api/v1/webhooks/incoming/"):
                rate_limit = ("webhook", settings.webhook_rate_limit_per_minute)
        if rate_limit:
            category, limit = rate_limit
            client_ip = request.client.host if request.client else "unknown"
            allowed, remaining, retry_after = await rate_limiter.check(
                f"{category}:{client_ip}", max(1, limit), 60
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests",
                            "details": {},
                        }
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms}"
        if rate_limit:
            response.headers["X-RateLimit-Limit"] = str(rate_limit[1])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        logger.info(
            "request completed method=%s path=%s status=%s duration_ms=%s correlation_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            correlation_id,
        )
        return response

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
