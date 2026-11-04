from __future__ import annotations

import logging
from typing import Any

from app.queue.base import TaskQueue

logger = logging.getLogger("agenthub.queue.arq")


class ArqTaskQueue(TaskQueue):
    """Redis/ARQ adapter used only when APP_MODE=docker.

    The import happens inside the constructor so the local mode (no redis/arq
    installed) imports this module without side effects. This adapter has not
    been exercised on the development machine: no Docker, Redis or Postgres
    are available there. See README, section "Docker contour".
    """

    name = "arq+redis"

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._redis = None

    async def _client(self):
        if self._redis is None:
            from arq import create_pool
            from arq.connections import RedisSettings

            self._redis = await create_pool(RedisSettings.from_dsn(self.redis_url))
        return self._redis

    async def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        client = await self._client()
        job = await client.enqueue_job(task_name, **payload)
        logger.info("queued %s as %s", task_name, job.job_id)
        return str(job.job_id)

    async def health(self) -> bool:
        try:
            client = await self._client()
            return bool(await client.ping())
        except Exception:  # noqa: BLE001 - health must never raise
            return False

    def start(self) -> None:
        return None

    async def stop(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
