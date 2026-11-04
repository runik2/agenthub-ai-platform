from __future__ import annotations

import json
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
            from redis.asyncio import from_url  # local import is intentional

            self._redis = from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        client = await self._client()
        job = {"task": task_name, "payload": payload}
        job_id = await client.rpush("agenthub:jobs", json.dumps(job))
        logger.info("queued %s as position %s", task_name, job_id)
        return str(job_id)

    async def health(self) -> bool:
        try:
            client = await self._client()
            return bool(await client.ping())
        except Exception:  # noqa: BLE001 - health must never raise
            return False
