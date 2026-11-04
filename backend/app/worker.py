"""ARQ worker entry point for APP_MODE=docker.

Stage 1-2 ships no background tasks yet (tasks/workflows arrive in stage 3),
so the worker only proves the queue is wired: it registers a `ping` job and
uses Redis health checks. Not verified locally — no Docker/Redis on the
development machine.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger("agenthub.worker")


async def ping(ctx: Any = None) -> str:
    logger.info("worker ping")
    return "pong"


async def execute_task(ctx: Any, task_id: str) -> None:
    from app.services.tasks import execute_task as run

    await run(task_id)


class WorkerSettings:
    functions = [ping, execute_task]
    redis_settings = None  # filled below

    @staticmethod
    def build() -> type[WorkerSettings]:
        from arq.connections import RedisSettings

        settings = get_settings()
        redis_url = getattr(settings, "redis_url", "redis://redis:6379/0")
        WorkerSettings.redis_settings = RedisSettings.from_dsn(redis_url)
        return WorkerSettings


try:
    settings_obj = WorkerSettings.build()
except ImportError:  # ARQ is optional in local/test installations.
    settings_obj = WorkerSettings
